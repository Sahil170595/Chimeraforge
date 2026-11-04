"""Original-N GET-only inspection with independent intent and native process ownership."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import math
import os
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
import time
from typing import Any

from chimeraforge import __version__
from chimeraforge.deployment_verify import _absolute, _json, _source
from chimeraforge.kubernetes_inspection_intent import (
    CLIENT_VERSION,
    SERVER_VERSION,
    compare_intent,
    rollout,
)
from chimeraforge.kubernetes_inspection_process import (
    MAX_PROCESSES,
    MAX_STDOUT_BYTES,
    MAX_STDERR_BYTES,
    MAX_TOTAL_BYTES,
    NativeOutput,
    ProcessOwner,
)
from chimeraforge.kubernetes_inspection_types import (
    KIND,
    KubernetesInspection,
    KubernetesInspectionError,
    verdict,
)
from chimeraforge.kubernetes_options import KubernetesOptions

LOG = logging.getLogger(__name__)
MAX_CONTEXT_CHARS = 253
MAX_PATH_CHARS = 4096
MAX_TIMEOUT_SECONDS = 600.0
MAX_REQUEST_SECONDS = 60.0
MAX_CLEANUP_SECONDS = 10.0
MIN_NATIVE_SECONDS = 0.001
MAX_CONCURRENCY = 4
PROVIDER_TEMPLATE = (
    '{{range .users}}{{if exists .user "auth-provider"}}provider_present'
    "{{else}}provider_absent{{end}}{{else}}provider_absent{{end}}"
)
CA_PATHS = "{.clusters[*].cluster['certificate-authority']}"
USER_PATHS = "{.users[*].user['client-certificate','client-key','tokenFile']}"
PREFERENCE = {
    "apiVersion": "kubectl.config.k8s.io/v1beta1",
    "kind": "Preference",
    "credentialPluginPolicy": "DenyAll",
}


class _OutputAdmissionError(KubernetesInspectionError):
    """A known output aliases a held input before any native process launch."""


def _number(value: object, maximum: float) -> bool:
    return (
        isinstance(value, (int, float))
        and type(value) in (int, float)
        and math.isfinite(value)
        and 0 < value <= maximum
    )


def _text(value: object, maximum: int) -> bool:
    return (
        type(value) is str
        and 0 < len(value) <= maximum
        and not any(ord(c) < 32 or ord(c) == 127 for c in value)
    )


def _protect(outputs: tuple[Path, ...], inputs: tuple[Path, ...]) -> None:
    from chimeraforge.plan_study import protect_output

    for index, output in enumerate(outputs):
        protect_output(output, (*inputs, *outputs[:index], *outputs[index + 1 :]))


def _references(raw: bytes, count: int, config: Path) -> tuple[Path, ...]:
    values = json.loads(raw.decode("utf-8"))
    if (
        type(values) is not list
        or len(values) > count
        or any(not _text(value, MAX_PATH_CHARS) for value in values)
    ):
        raise ValueError("native private path projection invalid")
    return tuple(
        _absolute(Path(value) if Path(value).is_absolute() else config.parent / value)
        for value in values
    )


def _child_environment(root: Path) -> dict[str, str]:
    # Native Load still migrates legacy home paths before reading ExplicitPath.
    excluded = {
        "HOME",
        "USERPROFILE",
        "HOMEDRIVE",
        "HOMEPATH",
        "KUBECONFIG",
        "KUBERC",
        "KUBECTL_KUBERC",
    }
    env = {key: value for key, value in os.environ.items() if key.upper() not in excluded}
    env.update(HOME=str(root / "home"), USERPROFILE=str(root / "home"), KUBECTL_KUBERC="true")
    return env


def _empty_row(index: int, expected: dict) -> dict[str, Any]:
    return {
        "index": index,
        "member_index": index // 2,
        "kind": expected["kind"],
        "name": expected["metadata"]["name"],
        "namespace": expected["metadata"]["namespace"],
        "observation": {
            "state": "unstarted",
            "reason": "preflight_unavailable",
            "object_sha256": None,
            "object_bytes": None,
        },
        "intent": {
            "state": "unknown",
            "reason": "observation_unavailable",
            "changes": [],
            "change_count": 0,
        },
        "rollout": {
            "state": "not_requested" if expected["kind"] == "Service" else "unknown",
            "reason": None,
        },
    }


async def inspect_kubernetes_deployment(
    saved: Any,
    *,
    image: str,
    kubeconfig: str | Path,
    context: str,
    kubernetes: KubernetesOptions | None = None,
    candidate_index: int = 0,
    model: str | None = None,
    kubectl: str | Path = "kubectl",
    timeout_s: float = 30,
    request_timeout_s: float = 10,
    concurrency: int = 4,
    cleanup_timeout_s: float = 2,
    stop_event: asyncio.Event | None = None,
    _outputs: tuple[str | Path, ...] = (),
) -> KubernetesInspection:
    """Observe 2N named resources; native discovery may issue additional read requests."""
    from chimeraforge.deploy import export_deployment
    from chimeraforge.bench.fleet_campaign_types import canonical_hash

    started = time.perf_counter()
    try:
        if (
            not _number(timeout_s, MAX_TIMEOUT_SECONDS)
            or not _number(request_timeout_s, MAX_REQUEST_SECONDS)
            or request_timeout_s < MIN_NATIVE_SECONDS
            or not _number(cleanup_timeout_s, MAX_CLEANUP_SECONDS)
            or type(concurrency) is not int
            or not 1 <= concurrency <= MAX_CONCURRENCY
            or not _text(context, MAX_CONTEXT_CHARS)
            or not isinstance(kubectl, (str, Path))
            or not _text(str(kubectl), MAX_PATH_CHARS)
            or (stop_event is not None and not isinstance(stop_event, asyncio.Event))
        ):
            raise ValueError("invalid inspection control")
        config = _absolute(kubeconfig)
        selected = shutil.which(str(kubectl))
        client_path = _absolute(selected) if selected is not None else None
        outputs = tuple(_absolute(value) for value in _outputs)
        artifact, source_raw, source_path = _source(saved)
        declaration = export_deployment(
            artifact,
            format="kubernetes",
            image=image,
            candidate_index=candidate_index,
            model=model,
            kubernetes=kubernetes,
        )
        expected = json.loads(declaration.content)["items"]
        candidate = artifact.candidate(candidate_index)
        guards = (
            (config,)
            + ((source_path,) if source_path is not None else ())
            + ((client_path,) if client_path is not None else ())
        )
    except Exception as exc:
        LOG.info("Kubernetes independent inspection intent refused (%s)", type(exc).__name__)
        raise KubernetesInspectionError(
            "invalid independent Kubernetes inspection intent"
        ) from None
    try:
        _protect(outputs, guards)
    except Exception as exc:
        LOG.info("Kubernetes inspection output admission refused (%s)", type(exc).__name__)
        raise _OutputAdmissionError("unsafe inspection output") from None

    data: dict[str, Any] = {
        "schema_version": 1,
        "kind": KIND,
        "tool_version": __version__,
        "exit_code": 4,
        "state": "unavailable",
        "plan": {
            "fingerprint": artifact._data["fingerprint"],
            "source_sha256": hashlib.sha256(source_raw).hexdigest(),
            "source_basis": "file_bytes" if source_path is not None else "artifact_snapshot",
            "candidate_index": candidate_index,
            "n_agents": candidate.n_agents,
            "tensor_parallel": candidate.tensor_parallel,
            "pipeline_parallel": candidate.pipeline_parallel,
        },
        "intent": {
            "render_sha256": hashlib.sha256(declaration.content.encode("utf-8")).hexdigest(),
            "namespace": expected[0]["metadata"]["namespace"],
            "image": image,
        },
        "controls": {
            "timeout_seconds": timeout_s,
            "request_timeout_seconds": request_timeout_s,
            "concurrency": concurrency,
            "cleanup_seconds": cleanup_timeout_s,
            "max_processes": MAX_PROCESSES,
            "max_stdout_bytes": MAX_STDOUT_BYTES,
            "max_stderr_bytes": MAX_STDERR_BYTES,
            "max_total_bytes": MAX_TOTAL_BYTES,
        },
        "preflight": {
            "complete": False,
            "reason": "native_preflight_unavailable",
            "client_version": None,
            "server_version": None,
            "private_projection_complete": False,
        },
        "budget": {"termination": None, "processes": 0, "bytes_read": 0, "elapsed_seconds": 0.0},
        "cleanup": {},
        "resources": [_empty_row(index, row) for index, row in enumerate(expected)],
    }
    owner = ProcessOwner(started + timeout_s, concurrency, cleanup_timeout_s, stop_event)
    directory: TemporaryDirectory[str] | None = None
    cancelled = False
    if stop_event is not None and stop_event.is_set():
        owner.stop("caller_stop")
    if owner.remaining() <= 0:
        owner.stop("observation_deadline")

    try:
        directory = TemporaryDirectory(prefix="chimeraforge-inspect-")
        root = Path(directory.name)
        (root / "home").mkdir()
        (root / "cache").mkdir()
        policy = root / "preferences.json"
        policy.write_text(json.dumps(PREFERENCE), encoding="utf-8")
        env = _child_environment(root)
        common = [
            str(client_path),
            "--kubeconfig",
            str(config),
            "--context",
            context,
            "--namespace",
            data["intent"]["namespace"],
            "--kuberc",
            str(policy),
            "--cache-dir",
            str(root / "cache"),
        ]

        async def command(args: list[str]) -> NativeOutput:
            def argv(remaining: float) -> list[str]:
                seconds = min(request_timeout_s, remaining)
                if seconds < MIN_NATIVE_SECONDS:
                    owner.stop("observation_deadline")
                    return []
                return [*common, f"--request-timeout={seconds:.6f}s", *args]

            return await owner.run(argv, env)

        async def preflight() -> bool:
            if client_path is None:
                data["preflight"]["reason"] = "native_client_unavailable"
                return False
            result = await command(["version", "--client=true", "--output=json"])
            if result.state != "complete":
                data["preflight"]["reason"] = result.reason
                return False
            client = _json(result.stdout, MAX_STDOUT_BYTES).get("clientVersion", {})
            if type(client) is not dict or client.get("gitVersion") != CLIENT_VERSION:
                data["preflight"]["reason"] = "unsupported_client_profile"
                return False
            data["preflight"]["client_version"] = CLIENT_VERSION
            view = [
                "config",
                "view",
                "--minify=true",
                "--merge=false",
                "--raw=false",
                "--flatten=false",
            ]
            provider = await command(
                [*view, "--output=go-template", "--template", PROVIDER_TEMPLATE]
            )
            if provider.state != "complete" or provider.stdout != b"provider_absent":
                data["preflight"]["reason"] = (
                    "legacy_auth_provider_unsupported"
                    if provider.state == "complete" and provider.stdout == b"provider_present"
                    else "private_config_projection_unavailable"
                )
                return False
            paths: list[Path] = []
            for expression, maximum in ((CA_PATHS, 1), (USER_PATHS, 3)):
                result = await command(
                    [*view, "--output=jsonpath-as-json", "--template", expression]
                )
                if result.state != "complete":
                    data["preflight"]["reason"] = "private_config_projection_unavailable"
                    return False
                paths.extend(_references(result.stdout, maximum, config))
            nonlocal guards
            guards = (*guards, *paths)
            _protect(outputs, guards)
            data["preflight"]["private_projection_complete"] = True
            result = await command(["version", "--output=json"])
            if result.state != "complete":
                data["preflight"]["reason"] = result.reason
                return False
            versions = _json(result.stdout, MAX_STDOUT_BYTES)
            if (
                versions.get("serverVersion", {}).get("gitVersion") != SERVER_VERSION
                or versions.get("clientVersion", {}).get("gitVersion") != CLIENT_VERSION
            ):
                data["preflight"]["reason"] = "unsupported_server_profile"
                return False
            data["preflight"].update(complete=True, reason=None, server_version=SERVER_VERSION)
            return True

        async def resource(index: int) -> None:
            row, intent = data["resources"][index], expected[index]
            kind = "deployments.apps" if row["kind"] == "Deployment" else "services"
            result = await command(
                ["get", kind, row["name"], "--ignore-not-found=true", "--output=json"]
            )
            row["observation"].update(state=result.state, reason=result.reason)
            if result.state != "complete":
                return
            if not result.stdout.strip():
                row["intent"].update(state="missing", reason="successful_named_resource_absent")
                return
            row["observation"].update(
                object_sha256=hashlib.sha256(result.stdout).hexdigest(),
                object_bytes=len(result.stdout),
            )
            try:
                actual = _json(result.stdout, MAX_STDOUT_BYTES)
                compared = compare_intent(intent, actual)
                row["intent"] = compared
                row["rollout"] = rollout(actual)
            except Exception as exc:
                LOG.info("Kubernetes named resource unavailable (%s)", type(exc).__name__)
                row["observation"].update(state="unavailable", reason="native_object_invalid")

        if await preflight():
            workers = [owner.task(resource(index)) for index in range(len(expected))]
            finished = asyncio.gather(*workers, return_exceptions=True)
            owner.joins.append(finished)
            await owner._wait(finished)
    except asyncio.CancelledError:
        cancelled = True
        owner.stop("caller_cancelled")
    except Exception as exc:
        LOG.info("Kubernetes native inspection unavailable (%s)", type(exc).__name__)
        data["preflight"]["reason"] = "native_preflight_invalid"
    finally:
        observed_until = time.perf_counter()
        if observed_until >= owner.deadline:
            owner.stop("observation_deadline")
        cleanup_deadline = time.perf_counter() + cleanup_timeout_s
        closer = asyncio.create_task(owner.close())
        while True:
            try:
                data["cleanup"] = await asyncio.shield(closer)
                break
            except asyncio.CancelledError:
                cancelled = True
        try:
            if directory is not None:
                directory.cleanup()
            data["cleanup"]["runtime_files_closed"] = True
        except OSError as exc:
            LOG.info("Kubernetes owned runtime files close failed (%s)", type(exc).__name__)
            data["cleanup"]["state"] = "incomplete"
        if time.perf_counter() > cleanup_deadline:
            data["cleanup"].update(allowance_exceeded=True, state="incomplete")
    if cancelled:
        raise asyncio.CancelledError
    if stop_event is not None and stop_event.is_set():
        owner.stop("caller_stop")
    for row in data["resources"]:
        if row["observation"]["state"] == "unstarted" and data["preflight"]["complete"]:
            row["observation"]["reason"] = owner.reason or "native_observation_unavailable"
    data["budget"].update(
        termination=owner.reason,
        processes=len(owner.children),
        bytes_read=owner.total_bytes,
        elapsed_seconds=time.perf_counter() - started,
        observation_elapsed_seconds=observed_until - started,
    )
    data["exit_code"] = verdict(data)
    data["state"] = {0: "match", 4: "unavailable", 5: "drift"}[data["exit_code"]]
    data["intent"]["fingerprint"] = canonical_hash(data["intent"])
    return KubernetesInspection(data, guards, data["preflight"]["private_projection_complete"])
