"""CLI for queried inventory mapping and saved batch-one memory arithmetic."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import cast

import typer


def inventory_check(
    plan: Path = typer.Option(..., "--plan", help="Original saved-plan JSON."),
    candidate_index: int = typer.Option(0, "--candidate-index"),
    gpu_device: list[str] | None = typer.Option(
        None, "--gpu-device", help="Ordered selector for one replica; repeat."
    ),
    replica_devices: list[str] | None = typer.Option(
        None,
        "--replica-devices",
        help="Ordered comma-separated selectors per original replica; repeat.",
    ),
    timeout: float = typer.Option(
        10.0, "--timeout", help="Native observation seconds, at most 60."
    ),
    memory_basis: str = typer.Option(
        "batch-one",
        "--memory-basis",
        help="batch-one (default) or selected-batch modeled resident components.",
    ),
    inventory_file: Path | None = typer.Option(
        None, "--inventory-file", help="Read a complete nvidia-smi CSV capture instead of querying."
    ),
    output_json: bool = typer.Option(False, "--json"),
) -> None:
    """Compare reported inventory with saved resident memory; no deployment readiness."""
    from chimeraforge import api
    from chimeraforge.commands.deploy import _replica_groups
    from chimeraforge.deploy import DeploymentError

    try:
        report = asyncio.run(
            api.check_inventory(
                plan,
                candidate_index=candidate_index,
                gpu_devices=gpu_device,
                replica_gpu_devices=_replica_groups(replica_devices),
                timeout=timeout,
                memory_basis=cast(api.MemoryBasis, memory_basis),
                inventory_file=inventory_file,
            )
        )
    except (api.InventoryCheckError, DeploymentError) as exc:
        error = (
            "Invalid inventory memory basis; choose batch-one or selected-batch."
            if memory_basis not in ("batch-one", "selected-batch")
            else "Invalid saved inventory source or selector declarations."
        )
        typer.echo(
            json.dumps(
                {
                    "outcome": "invalid",
                    "exit_code": 1,
                    "error": error,
                }
            )
            if output_json
            else error
        )
        raise typer.Exit(1) from exc
    if output_json:
        typer.echo(json.dumps(report.to_dict(), allow_nan=False))
    else:
        if isinstance(report.observation, api.InventoryCaptureObservation):
            typer.echo(f"Supplied inventory CSV: {report.observation.state}.")
        typer.echo(f"Inventory arithmetic {report.outcome}; deployment readiness is unassessed.")
        if isinstance(report.baseline, api.SelectedBatchBaseline):
            baseline = report.baseline
            selected = (
                f"{baseline.selected_lower_gib}..{baseline.selected_upper_gib} "
                f"GiB per entry ({baseline.status})"
                if baseline.status == "estimated"
                else f"unavailable ({baseline.reason})"
            )
            typer.echo(
                f"Selected batch B={baseline.saved_effective_batch}, "
                f"context={baseline.saved_context_length}: {selected}."
            )
            typer.echo(
                f"Original saved B1: {baseline.saved_batch1.lower_gib}.."
                f"{baseline.saved_batch1.upper_gib} GiB per entry."
            )
            typer.echo(
                "Selected increment uses full saved context per active sequence; unassessed: "
                + ", ".join(baseline.unassessed_residency)
                + "."
            )
        else:
            typer.echo(
                f"Saved B1 baseline: {report.baseline.lower_gib}.."
                f"{report.baseline.upper_gib} GiB per entry."
            )
        for slot in report.slots:
            typer.echo(
                f"Replica {slot.replica_index} device {slot.device_index}: "
                f"{slot.selector} {slot.selector_state}; free {slot.free_comparison}; "
                f"{','.join(slot.reasons)}"
            )
        typer.echo("Unassessed: " + ", ".join(report.unassessed))
    raise typer.Exit(report.exit_code)
