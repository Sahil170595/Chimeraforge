"""Operator-authored serving declarations, dated quotes and native configurations."""

from __future__ import annotations

import json
from pathlib import Path

import typer

serving_app = typer.Typer(help="Declare serving intent without an optimizer or capacity claim.")


def _error(output_json: bool) -> None:
    typer.echo(
        json.dumps({"exit_code": 1, "error": "Invalid serving input or output."})
        if output_json
        else "Invalid serving input or output."
    )
    raise typer.Exit(1)


@serving_app.command("declare")
def declare(
    model: str = typer.Option(..., "--model"),
    revision: str = typer.Option(
        ..., "--revision", help="Operator-claimed lowercase40hex HF commit."
    ),
    backend: str = typer.Option(..., "--backend", help="vllm or sglang."),
    image: str = typer.Option(
        ..., "--image", help="Explicit non-latest tag or sha256 digest; compatibility unknown."
    ),
    out: Path = typer.Option(..., "--out", help="New operator declaration JSON file."),
    replicas: int = typer.Option(1, "--replicas"),
    tp: int = typer.Option(1, "--tp"),
    pp: int = typer.Option(1, "--pp"),
    context: int = typer.Option(4096, "--context"),
    batch: int = typer.Option(1, "--batch"),
    dtype: str = typer.Option("FP16", "--dtype"),
    kv_quant: str = typer.Option("fp16", "--kv-quant"),
    prefix_caching: bool = typer.Option(False, "--prefix-caching"),
    max_num_batched_tokens: int | None = typer.Option(None, "--max-num-batched-tokens"),
    output_json: bool = typer.Option(False, "--json"),
) -> None:
    """Save closed concrete settings; no model/config/corpus lookup or optimization."""
    from chimeraforge.api import ServingRequest, declare_serving

    try:
        declaration = declare_serving(
            ServingRequest(
                model,
                revision,
                backend,
                image,
                replicas,
                tp,
                pp,
                context,
                batch,
                dtype,
                kv_quant,
                prefix_caching,
                max_num_batched_tokens,
            )
        )
        declaration.save(out)
    except (ValueError, OSError, TypeError):
        _error(output_json)
    result = {
        "status": "operator_declared",
        "fingerprint": declaration.fingerprint,
        "logical_gpu_slots": replicas * tp * pp,
        "deployment_ready": None,
    }
    typer.echo(
        json.dumps(result)
        if output_json
        else (
            f"Serving declaration saved: {replicas} replicas, "
            f"{replicas * tp * pp} logical GPU slots; "
            "capacity unknown."
        )
    )


@serving_app.command("quote")
def quote(
    declaration: Path = typer.Option(..., "--declaration"),
    cloud: str | None = typer.Option(None, "--cloud"),
    instance: str | None = typer.Option(None, "--instance"),
    region: str | None = typer.Option(None, "--region"),
    output_json: bool = typer.Option(False, "--json"),
) -> None:
    """Quote an exact dated billing target; no replica-to-host placement."""
    from chimeraforge.api import quote_serving

    try:
        result = quote_serving(declaration, cloud=cloud, instance=instance, region=region).to_dict()
    except (ValueError, OSError, TypeError, KeyError):
        _error(output_json)
    typer.echo(
        json.dumps(result)
        if output_json
        else f"Serving quote {result['status']}: {result['reason']}; feasibility unknown."
    )


@serving_app.command("export")
def export(
    declaration: Path = typer.Option(..., "--declaration"),
    format: str = typer.Option(..., "--format", help="launch, compose or kubernetes."),
    out: Path = typer.Option(..., "--out"),
    gpu_device: list[str] | None = typer.Option(None, "--gpu-device"),
    host_port: int | None = typer.Option(None, "--host-port"),
    replica_devices: list[str] | None = typer.Option(None, "--replica-devices"),
    replica_port: list[int] | None = typer.Option(None, "--replica-port"),
    namespace: str | None = typer.Option(None, "--namespace"),
    name_prefix: str | None = typer.Option(None, "--name-prefix"),
    node_selector: list[str] | None = typer.Option(None, "--node-selector"),
    output_json: bool = typer.Option(False, "--json"),
) -> None:
    """Write explicit per-replica launch or native Compose/Kubernetes config, never execute it."""
    from chimeraforge.api import export_serving_declaration
    from chimeraforge.commands.deploy import _replica_groups, _kubernetes_options
    from chimeraforge.deployment_verify import _absolute, _aliases

    try:
        _aliases([_absolute(declaration), _absolute(out)])
        result = export_serving_declaration(
            declaration,
            format=format,
            gpu_devices=gpu_device,
            host_port=host_port,
            replica_gpu_devices=_replica_groups(replica_devices),
            replica_host_ports=replica_port,
            kubernetes=_kubernetes_options(namespace, name_prefix, node_selector),
        )
        with out.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(result.content)
    except (ValueError, OSError, TypeError, KeyError):
        _error(output_json)
    typer.echo(
        json.dumps({"status": "exported", "format": format, "deployment_ready": None})
        if output_json
        else "Serving configuration exported; runtime and capacity remain unverified."
    )


@serving_app.command("verify")
def verify(
    declaration: Path = typer.Option(..., "--declaration"),
    config: Path = typer.Option(..., "--config"),
    format: str = typer.Option("compose", "--format"),
    gpu_device: list[str] | None = typer.Option(None, "--gpu-device"),
    host_port: int | None = typer.Option(None, "--host-port"),
    replica_devices: list[str] | None = typer.Option(None, "--replica-devices"),
    replica_port: list[int] | None = typer.Option(None, "--replica-port"),
    namespace: str | None = typer.Option(None, "--namespace"),
    name_prefix: str | None = typer.Option(None, "--name-prefix"),
    node_selector: list[str] | None = typer.Option(None, "--node-selector"),
    output_json: bool = typer.Option(False, "--json"),
) -> None:
    """Verify held original intent against config; match0, drift5, invalid1."""
    from chimeraforge.api import verify_serving_declaration
    from chimeraforge.commands.deploy import _replica_groups, _kubernetes_options

    try:
        result = verify_serving_declaration(
            declaration,
            config,
            format=format,
            gpu_devices=gpu_device,
            host_port=host_port,
            replica_gpu_devices=_replica_groups(replica_devices),
            replica_host_ports=replica_port,
            kubernetes=_kubernetes_options(namespace, name_prefix, node_selector),
        )
    except (ValueError, OSError, TypeError, KeyError):
        _error(output_json)
    typer.echo(
        json.dumps(result.to_dict())
        if output_json
        else f"Serving config {result.status}: {result.change_count} changes; no runtime proof."
    )
    raise typer.Exit(result.exit_code)
