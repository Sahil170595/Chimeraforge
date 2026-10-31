"""Read-only native Kubernetes inspection with explicit independent declaration intent."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

import typer

LOG = logging.getLogger(__name__)


def deploy_inspect(
    plan: Path = typer.Option(..., "--plan", help="Original saved plan."),
    image: str = typer.Option(..., "--image", help="Independent expected non-latest image."),
    kubeconfig: Path = typer.Option(
        ..., "--kubeconfig", help="Explicit runtime credential config."
    ),
    context: str = typer.Option(
        ..., "--context", help="Explicit runtime context; never persisted."
    ),
    namespace: str = typer.Option(
        "default", "--namespace", help="Independent namespace, not ambient context."
    ),
    name_prefix: str | None = typer.Option(None, "--name-prefix"),
    node_selector: list[str] | None = typer.Option(
        None, "--node-selector", help="Independent key=value; repeat."
    ),
    candidate_index: int = typer.Option(0, "--candidate-index"),
    model: str | None = typer.Option(
        None, "--model", help="Independent concrete serving identity."
    ),
    kubectl: str = typer.Option(
        "kubectl", "--kubectl", help="Installed native kubectl executable."
    ),
    timeout: float = typer.Option(30, "--timeout", help="Whole observation budget in seconds."),
    request_timeout: float = typer.Option(
        10, "--request-timeout", help="Native per-request seconds, clipped to budget."
    ),
    concurrency: int = typer.Option(4, "--concurrency"),
    cleanup_timeout: float = typer.Option(
        2, "--cleanup-timeout", help="Cooperative cleanup allowance, not hard return."
    ),
    out: Path | None = typer.Option(None, "--out", help="Complete bounded JSON destination."),
    junit: Path | None = typer.Option(None, "--junit", help="All original intent/rollout cases."),
    output_json: bool = typer.Option(False, "--json", help="Emit exact bounded JSON bytes."),
) -> None:
    """Inspect original Deployments/Services using GET only; no scheduling/GPU proof."""
    from chimeraforge.api import PlanError
    from chimeraforge.commands.deploy import _kubernetes_options
    from chimeraforge.deploy import DeploymentError
    from chimeraforge.kubernetes_inspection import (
        inspect_kubernetes_deployment,
        _protect,
        _OutputAdmissionError,
    )
    from chimeraforge.kubernetes_inspection_output import publish
    from chimeraforge.kubernetes_inspection_types import KubernetesInspectionError
    from chimeraforge.deployment_verify import _absolute

    outputs = tuple(path for path in (out, junit) if path is not None)
    try:
        _protect(
            tuple(_absolute(path) for path in outputs), (_absolute(plan), _absolute(kubeconfig))
        )
    except (PlanError, ValueError, OSError) as exc:
        LOG.info("Kubernetes inspection output admission refused (%s)", type(exc).__name__)
        typer.echo(json.dumps({"exit_code": 2, "error": "Unsafe inspection output."}))
        raise typer.Exit(2) from None
    try:
        result = asyncio.run(
            inspect_kubernetes_deployment(
                plan,
                image=image,
                kubeconfig=kubeconfig,
                context=context,
                kubernetes=_kubernetes_options(namespace, name_prefix, node_selector),
                candidate_index=candidate_index,
                model=model,
                kubectl=kubectl,
                timeout_s=timeout,
                request_timeout_s=request_timeout,
                concurrency=concurrency,
                cleanup_timeout_s=cleanup_timeout,
                _outputs=outputs,
            )
        )
    except _OutputAdmissionError:
        typer.echo(json.dumps({"exit_code": 2, "error": "Unsafe inspection output."}))
        raise typer.Exit(2) from None
    except (KubernetesInspectionError, DeploymentError) as exc:
        LOG.info("Kubernetes inspection input refused (%s)", type(exc).__name__)
        typer.echo(json.dumps({"exit_code": 1, "error": "Invalid independent inspection intent."}))
        raise typer.Exit(1) from None
    try:
        raw = publish(result, out=out, junit=junit)
    except KubernetesInspectionError:
        typer.echo(json.dumps({"exit_code": 2, "error": "Cannot publish complete inspection."}))
        raise typer.Exit(2) from None
    if output_json:
        typer.echo(raw, nl=False)
    else:
        typer.echo(
            f"Kubernetes inspection {result._data['state']}; "
            f"{len(result.resources)} original resources; exit {result.exit_code}."
        )
    raise typer.Exit(result.exit_code)
