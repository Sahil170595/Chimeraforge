"""Offline weight-space artifact commands."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from chimeraforge.weightspace import ManifestError, estimate_footprint, verify_bundle

weightspace_app = typer.Typer(help="Inspect local weight-space artifacts.", no_args_is_help=True)


@weightspace_app.command()
def verify(
    manifest: Path = typer.Argument(...),
    root: Path | None = typer.Option(None, help="Directory containing the declared files."),
    expected_sha256: str | None = typer.Option(None, help="Externally supplied manifest SHA-256."),
) -> None:
    """Verify every declared file's size and SHA-256 offline and emit a JSON receipt."""
    try:
        result = verify_bundle(manifest, root, expected_sha256=expected_sha256)
    except ManifestError as exc:
        typer.echo(json.dumps({"status": "invalid", "error": str(exc)}))
        raise typer.Exit(1) from exc
    typer.echo(json.dumps(result.to_dict()))


@weightspace_app.command()
def footprint(
    manifest: Path = typer.Argument(...),
    root: Path | None = typer.Option(None),
    expected_sha256: str | None = typer.Option(None),
    cached_sha256: list[str] | None = typer.Option(
        None, help="Already-held content digest. Repeat for multiple files."
    ),
) -> None:
    """Estimate transfer, storage, and declared materialization sizes in bytes."""
    try:
        result = estimate_footprint(
            manifest, root, expected_sha256=expected_sha256, cached_sha256=cached_sha256 or ()
        )
    except ManifestError as exc:
        typer.echo(json.dumps({"status": "invalid", "error": str(exc)}))
        raise typer.Exit(1) from exc
    typer.echo(json.dumps(result.to_dict()))
