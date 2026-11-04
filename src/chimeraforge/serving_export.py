"""Native serving declarations and bounded config verification, without optimization."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import json
from pathlib import Path

from chimeraforge.deploy import (
    DeploymentError,
    DeploymentExport,
    _compose_service,
    _compose_value,
    _device_selection,
    _hf_argv,
    _image,
    _replica_layout,
    _validate_fidelity,
)
from chimeraforge.kubernetes_options import KubernetesOptions, admit_options
from chimeraforge.serving_declaration import (
    MAX_DECLARATION_BYTES,
    ServingDeclaration,
    ServingDeclarationError,
    declaration_from_dict,
    projection,
    receive,
)

FORMATS = ("launch", "compose", "kubernetes")
_NOTES = [
    "Operator declaration only: no model/config/corpus lookup, optimizer feasibility, "
    "measured throughput, quality, memory fit or SLO proof.",
    "Revision and image are operator claims. An explicit tag may move; a digest is not "
    "fetched or authenticated. Image/engine/driver/model compatibility remains unknown.",
    "Whole-instance quotes do not assign hosts. Compose/launch device groups share one declared "
    "host namespace; a billed multi-instance fleet is not a host placement for that project.",
]


def export_serving_declaration(
    declaration: ServingDeclaration | str | Path,
    *,
    format: str,
    gpu_devices: list[str] | None = None,
    host_port: int | None = None,
    replica_gpu_devices: list[list[str]] | None = None,
    replica_host_ports: list[int] | None = None,
    kubernetes: KubernetesOptions | None = None,
) -> DeploymentExport:
    from chimeraforge.deployment_verify import MAX_CONFIG_BYTES, _admit
    from chimeraforge.kubernetes_export import render

    if format not in FORMATS:
        raise ServingDeclarationError("serving format must be launch, compose or kubernetes")
    if kubernetes is not None and format != "kubernetes":
        raise ServingDeclarationError("Kubernetes options apply only to Kubernetes")
    if format == "kubernetes" and any(
        value is not None
        for value in (gpu_devices, host_port, replica_gpu_devices, replica_host_ports)
    ):
        raise ServingDeclarationError(
            "Kubernetes uses logical GPU resources, not host device/port mappings"
        )
    if (replica_gpu_devices is not None or replica_host_ports is not None) and (
        gpu_devices is not None or host_port is not None
    ):
        raise ServingDeclarationError("singular and replica placement options cannot mix")
    try:
        held = receive(declaration)
        target, settings = projection(held)
        request = held.request
        _validate_fidelity(
            target, None, settings, "linux", "compose" if format == "launch" else format
        )
        image = _image(request.image)
        argv, notes = _hf_argv(
            target,
            None,
            request.model,
            settings,
            "127.0.0.1" if format == "launch" else "0.0.0.0",
            claimed_revision=request.revision,
        )
        if format == "kubernetes":
            options = kubernetes or KubernetesOptions()
            if isinstance(options, KubernetesOptions) and options.name_prefix is None:
                options = replace(options, name_prefix=f"cf-{held.fingerprint[:12]}-serving")
            options = admit_options(options, held.fingerprint, 0)
            content = render(target, argv, image, held.fingerprint, 0, options, declaration=True)
        else:
            if host_port is not None and (
                type(host_port) is not int or not 1 <= host_port <= 65535
            ):
                raise ServingDeclarationError("invalid bounded host port")
            layout = _replica_layout(target, replica_gpu_devices, replica_host_ports)
            groups: list[list[str] | None]
            if layout is None:
                devices = _device_selection(gpu_devices, target.gpus_total)
                ports = [
                    host_port
                    if host_port is not None
                    else 8000
                    if target.backend == "vllm"
                    else 30000
                ]
                groups = [devices]
            else:
                groups = [group for group in layout[0]]
                ports = layout[1]
            if format == "compose":
                services = {}
                for index, (devices, port) in enumerate(zip(groups, ports), 1):
                    service = _compose_service(
                        target, argv, {}, image, held.fingerprint, devices, port, declaration=True
                    )
                    service["labels"].update(
                        {
                            "org.chimeraforge.replica-index": str(index),
                            "org.chimeraforge.replica-count": str(target.n_agents),
                        }
                    )
                    services["inference" if target.n_agents == 1 else f"inference-{index}"] = (
                        service
                    )
                content = json.dumps(_compose_value({"services": services}), indent=2) + "\n"
            else:
                entries = []
                for index, (devices, port) in enumerate(zip(groups, ports), 1):
                    native_argv = argv[:]
                    native_argv[native_argv.index("--port") + 1] = str(port)
                    selected = (
                        devices
                        if devices is not None
                        else [
                            str(i) for i in range(target.tensor_parallel * target.pipeline_parallel)
                        ]
                    )
                    entries.append(
                        {
                            "replica_index": index,
                            "argv": native_argv,
                            "environment": {"CUDA_VISIBLE_DEVICES": ",".join(selected)},
                            "host_port": port,
                            "logical_gpu_slots": len(selected),
                        }
                    )
                content = (
                    json.dumps(
                        {
                            "kind": "chimeraforge.serving-launch",
                            "declaration_fingerprint": held.fingerprint,
                            "host_namespace": (
                                "single operator-declared host; no host assignment from quote"
                            ),
                            "replicas": entries,
                            "deployment_ready": None,
                        },
                        indent=2,
                    )
                    + "\n"
                )
        encoded = content.encode("utf-8")
        if len(encoded) > MAX_CONFIG_BYTES:
            raise ServingDeclarationError("serving configuration exceeds native byte bound")
        _admit(json.loads(encoded), MAX_CONFIG_BYTES)
    except ServingDeclarationError:
        raise
    except (DeploymentError, OSError, ValueError, TypeError, KeyError, OverflowError, UnicodeError):
        raise ServingDeclarationError("invalid serving export") from None
    return DeploymentExport(format, request.backend, content, [*_NOTES, *notes])


@dataclass(frozen=True)
class ServingVerification:
    status: str
    exit_code: int
    renderer_version: str
    backend: str
    source_kind: str
    declaration_sha256: str
    config_sha256: str
    expected_config_sha256: str
    changes: tuple
    change_count: int
    changes_truncated: bool
    companions: tuple

    def to_dict(self) -> dict:
        return asdict(self)


def verify_serving_declaration(
    declaration: ServingDeclaration | str | Path,
    config_path: str | Path,
    *,
    format: str = "compose",
    gpu_devices: list[str] | None = None,
    host_port: int | None = None,
    replica_gpu_devices: list[list[str]] | None = None,
    replica_host_ports: list[int] | None = None,
    kubernetes: KubernetesOptions | None = None,
) -> ServingVerification:
    from chimeraforge.deployment_verify import _absolute, _aliases, _json, _verify_expected
    from chimeraforge.plan_bundle import _read

    if format not in FORMATS:
        raise ServingDeclarationError("invalid serving verification format")
    try:
        config = _absolute(config_path)
        source = None
        if type(declaration) is ServingDeclaration:
            raw = json.dumps(declaration.to_dict(), allow_nan=False).encode("utf-8")
        elif isinstance(declaration, (str, Path)):
            source = _absolute(declaration)
            _aliases([config, source])
            raw = _read(source, MAX_DECLARATION_BYTES)
        else:
            raise ServingDeclarationError("expected an original serving declaration")
        held = declaration_from_dict(_json(raw, MAX_DECLARATION_BYTES))
        expected = export_serving_declaration(
            held,
            format=format,
            gpu_devices=gpu_devices,
            host_port=host_port,
            replica_gpu_devices=replica_gpu_devices,
            replica_host_ports=replica_host_ports,
            kubernetes=kubernetes,
        )
        report = _verify_expected(expected, config, raw, source, format=format)
        data = report.to_dict()
        data["declaration_sha256"] = data.pop("plan_sha256")
        return ServingVerification(**data)
    except (OSError, ValueError, TypeError, KeyError, OverflowError, RecursionError, UnicodeError):
        raise ServingDeclarationError("invalid serving verification input") from None
