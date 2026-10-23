"""Read-only verification of a JSON Compose declaration against independent intent."""

from __future__ import annotations

import json
from pathlib import Path

import typer


def deploy_verify(
    plan: Path = typer.Option(..., "--plan", help="Original independently supplied saved plan."),
    config: Path = typer.Option(..., "--config", help="Existing generated JSON Compose file."),
    image: str = typer.Option(..., "--image", help="Independent expected image tag/digest."),
    model: str | None = typer.Option(None, "--model", help="Expected concrete serving identity."),
    candidate_index: int = typer.Option(0, "--candidate-index", help="Saved candidate index."),
    gpu_device: list[str] | None = typer.Option(
        None, "--gpu-device", help="Ordered expected GPU ID; repeat."
    ),
    host_port: int | None = typer.Option(
        None, "--host-port", help="Expected single Compose host port."
    ),
    replica_devices: list[str] | None = typer.Option(
        None, "--replica-devices", help="Expected comma-separated GPU group per replica."
    ),
    replica_port: list[int] | None = typer.Option(
        None, "--replica-port", help="Expected host port per replica."
    ),
    output_json: bool = typer.Option(False, "--json", help="Print a value-redacted JSON receipt."),
) -> None:
    """Compare current-renderer declarations; no interpolation, Docker or GPU calls."""
    from chimeraforge.commands.deploy import _replica_groups
    from chimeraforge.deploy import DeploymentError
    from chimeraforge.deployment_verify import DeploymentVerificationError, verify_deployment

    try:
        result = verify_deployment(
            plan,
            config,
            image=image,
            model=model,
            candidate_index=candidate_index,
            gpu_devices=gpu_device,
            host_port=host_port,
            replica_gpu_devices=_replica_groups(replica_devices),
            replica_host_ports=replica_port,
        )
    except (DeploymentVerificationError, DeploymentError) as exc:
        if output_json:
            typer.echo(
                json.dumps(
                    {
                        "status": "invalid",
                        "exit_code": 1,
                        "error": "Invalid deployment verification input.",
                    }
                )
            )
        else:
            typer.echo("Invalid deployment verification input.")
        raise typer.Exit(1) from exc
    if output_json:
        typer.echo(json.dumps(result.to_dict()))
    else:
        typer.echo(f"Deployment {result.status}: {result.change_count} changes.")
    raise typer.Exit(result.exit_code)
