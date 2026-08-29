"""`mcp` command - run the MCP server so assistants (Claude/GPT/Cursor) can call
the planner. Heavy/optional `mcp` SDK is imported lazily inside the command."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.markup import escape

console = Console()


def mcp() -> None:
    """Run the ChimeraForge MCP server over stdio.

    Exposes plan / resolve-model / list-hardware tools to any MCP client so an
    assistant answers deployment questions from measured data, not stale guesses.
    Requires the ``mcp`` extra: pip install "chimeraforge[mcp]".
    """
    from chimeraforge.mcp_server import main

    try:
        main()
    except RuntimeError as exc:  # missing `mcp` extra -> clean, actionable error
        console.print(f"[red]Error:[/] {escape(str(exc))}")
        raise typer.Exit(code=1)
