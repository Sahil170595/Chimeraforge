"""ChimeraForge CLI — Typer application.

The command implementations live in ``chimeraforge.commands.*``; this module
wires them onto the Typer ``app``. Heavy modules are imported lazily inside each
command to keep ``chimeraforge --version`` fast.
"""

from __future__ import annotations

import typer
from rich.console import Console

import chimeraforge
from chimeraforge.commands.bench import bench
from chimeraforge.commands.compare import compare
from chimeraforge.commands.eval import eval_cmd
from chimeraforge.commands.plan import plan
from chimeraforge.commands.refit import refit
from chimeraforge.commands.report import report

console = Console()

app = typer.Typer(
    name="chimeraforge",
    help="LLM deployment optimizer — backed by ~204,000 real measurements.",
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
    """ChimeraForge — LLM deployment optimizer."""


# Register commands (implementations in chimeraforge.commands.*).
# Order here is the order shown in `chimeraforge --help`.
app.command()(plan)
app.command()(bench)
app.command()(refit)
app.command()(compare)
app.command(name="eval")(eval_cmd)
app.command()(report)
