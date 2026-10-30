"""Saved-plan benchmark CLI routing and receipt presentation."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import typer
from click.core import ParameterSource
from rich.console import Console
from chimeraforge.monitor_connection import MonitorConnection


def run_saved(
    ctx: typer.Context,
    plan_path: str,
    *,
    candidate_index: int,
    model: str | None,
    backend: str,
    prompt: str | None,
    runs: int,
    workload: str,
    rate: float | None,
    concurrency: int | None,
    base_url: str | None,
    output_dir: str | None,
    output_json: bool,
    quant: str | None,
    all_quants: bool,
    context: str | None,
    list_backends: bool,
    connection: MonitorConnection | None = None,
) -> None:
    from chimeraforge.api import PlanError, benchmark_plan
    from chimeraforge.bench.serving import sanitize_message
    from chimeraforge.plan_study import protect_output

    def error(message: str, code: int) -> None:
        message = sanitize_message(message)
        if output_json:
            typer.echo(json.dumps({"error": message}))
        else:
            Console().print(message, markup=False)
        if connection is not None:
            raise typer.Exit(code) from None
        raise typer.Exit(code)

    if quant is not None or all_quants or context is not None or list_backends:
        error("--plan does not accept quant/context labels, sweeps or --list-backends.", 2)
    chosen_backend = (
        backend if ctx.get_parameter_source("backend") == ParameterSource.COMMANDLINE else None
    )
    if output_dir:
        directory = Path(output_dir)
    else:
        from platformdirs import user_data_dir

        directory = Path(user_data_dir("chimeraforge")) / "results"
    if connection is not None:
        try:
            protect_output(directory, (*connection._input_paths(), Path(plan_path)))
        except (PlanError, OSError):
            error("secure benchmark output unavailable", 1)
    try:
        receipt = asyncio.run(
            benchmark_plan(
                plan_path,
                candidate_index=candidate_index,
                model=model,
                backend=chosen_backend,
                prompt=prompt,
                runs=runs,
                workload=workload,
                rate=rate,
                concurrency=concurrency,
                base_url=base_url,
                **({"connection": connection} if connection is not None else {}),
            )
        )
    except PlanError as exc:
        error("secure saved benchmark input unavailable" if connection is not None else str(exc), 2)
    except (RuntimeError, ValueError) as exc:
        error("secure saved benchmark unavailable" if connection is not None else str(exc), 1)
    report = receipt.to_dict()
    if output_dir:
        directory = Path(output_dir)
    else:
        from platformdirs import user_data_dir

        directory = Path(user_data_dir("chimeraforge")) / "results"
    destination = directory / f"plan-bench_{report['fingerprint'][:16]}.json"
    try:
        directory.mkdir(parents=True, exist_ok=True)
        receipt.save(destination)
    except (PlanError, OSError) as exc:
        error("secure saved benchmark unavailable" if connection is not None else str(exc), 1)
    if output_json:
        typer.echo(json.dumps(report, allow_nan=False))
    else:
        console = Console()
        console.print(
            f"Benchmark: {report['status']}; configuration {report['configuration_status']}",
            markup=False,
        )
        console.print(
            f"Requests: {report['execution']['successful_count']}/"
            f"{report['execution']['requested_count']}"
        )
        for name, metric in report["audit"]["metrics"].items():
            console.print(
                f"{name}: modeled={metric['modeled']}, measured={metric['measured']} "
                f"{metric['unit']}; {metric['state']}",
                markup=False,
            )
        console.print(report["limits"], markup=False)
    Console(stderr=output_json).print(f"Receipt saved to: {destination}", markup=False)
    raise typer.Exit(report["exit_code"])
