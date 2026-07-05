"""Shared helpers for clean optional-dependency errors in CLI commands.

The serving backends import third-party deps (``httpx``) at module load, so a
command that needs an optional extra would otherwise surface a raw
``ModuleNotFoundError`` traceback instead of a clear "install the extra"
message. ``require_extra`` checks availability *without* importing (so no
traceback) and fails loud-and-clean, matching the resolver's behaviour.
"""

from __future__ import annotations

import importlib.util

import typer
from rich.console import Console
from rich.markup import escape

_console = Console()


def require_extra(extra: str, *modules: str) -> None:
    """Exit cleanly (code 1) if any *modules* for an optional *extra* is missing.

    Args:
        extra: The optional-dependency group name (e.g. ``"bench"``).
        modules: Import names the command needs (e.g. ``"httpx"``).
    """
    missing = [m for m in modules if importlib.util.find_spec(m) is None]
    if missing:
        # escape() so Rich does not swallow the ``[extra]`` as a style tag.
        hint = escape(f'pip install "chimeraforge[{extra}]"')
        _console.print(
            f"[red]Error:[/] this command needs the '{extra}' extra "
            f"({', '.join(missing)} not installed). {hint}"
        )
        raise typer.Exit(code=1)
