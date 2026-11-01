"""ChimeraForge CLI - Typer application.

The command implementations live in ``chimeraforge.commands.*``; this module
wires them onto the Typer ``app``. Heavy modules are imported lazily inside each
command to keep ``chimeraforge --version`` fast.
"""

from __future__ import annotations

import typer
from rich.console import Console

import chimeraforge
from chimeraforge.commands.bench import bench
from chimeraforge.commands.bundle import bundle_app
from chimeraforge.commands.catalog import catalog
from chimeraforge.commands.check import check
from chimeraforge.commands.compare import compare
from chimeraforge.commands.contribute import contribute_app
from chimeraforge.commands.doctor import doctor
from chimeraforge.commands.gate import gate
from chimeraforge.commands.deploy import deploy
from chimeraforge.commands.deploy_verify import deploy_verify
from chimeraforge.commands.deploy_inspect import deploy_inspect
from chimeraforge.commands.inventory_check import inventory_check
from chimeraforge.commands.eval import eval_cmd
from chimeraforge.commands.mcp import mcp
from chimeraforge.commands.monitor import monitor
from chimeraforge.commands.monitor_fleet import monitor_fleet
from chimeraforge.commands.trace_fleet import trace_fleet
from chimeraforge.commands.trace_fleet_campaign import trace_fleet_campaign
from chimeraforge.commands.measure import measure
from chimeraforge.commands.plan import plan
from chimeraforge.commands.refit import refit
from chimeraforge.commands.report import report
from chimeraforge.commands.workload import workload
from chimeraforge.commands.safety import safety
from chimeraforge.commands.score import score
from chimeraforge.commands.serve import serve
from chimeraforge.commands.suggest import suggest
from chimeraforge.commands.study import study
from chimeraforge.commands.trace import trace
from chimeraforge.commands.trace_campaign import trace_campaign
from chimeraforge.commands.trace_envelope import trace_envelope
from chimeraforge.commands.validate import validate

console = Console()

app = typer.Typer(
    name="chimeraforge",
    help="LLM deployment optimizer - backed by ~204,000 real measurements.",
    no_args_is_help=True,
    add_completion=False,
)


def version_callback(value: bool) -> None:
    if value:
        console.print(f"chimeraforge {chimeraforge.__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        help="Show version and exit.",
        callback=version_callback,
        is_eager=True,
    ),
) -> None:
    """ChimeraForge - LLM deployment optimizer."""


# Register commands (implementations in chimeraforge.commands.*).
# Order here is the order shown in `chimeraforge --help`.
app.command()(plan)
app.command()(check)
app.add_typer(bundle_app, name="bundle")
app.command()(study)
app.command()(deploy)
app.command("deploy-verify")(deploy_verify)
app.command("deploy-inspect")(deploy_inspect)
app.command("inventory-check")(inventory_check)
app.command()(suggest)
app.command()(measure)
app.command()(validate)
app.command()(catalog)
app.command()(safety)
app.command()(bench)
app.command()(trace)
app.command("trace-campaign")(trace_campaign)
app.command("trace-envelope")(trace_envelope)
app.command()(gate)
app.command()(score)
app.command()(refit)
app.command()(compare)
app.command(name="eval")(eval_cmd)
app.command()(report)
app.command()(workload)
app.command()(monitor)
app.command("monitor-fleet")(monitor_fleet)
app.command("trace-fleet")(trace_fleet)
app.command("trace-fleet-campaign")(trace_fleet_campaign)
app.command()(doctor)
app.add_typer(contribute_app, name="contribute")
app.command()(mcp)
app.command()(serve)


if __name__ == "__main__":  # pragma: no cover - module invocation
    app()
