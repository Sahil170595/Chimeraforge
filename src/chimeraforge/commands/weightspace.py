"""Offline weight-space artifact commands."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from chimeraforge.weightspace import (
    ManifestError,
    admit_adapter as check_adapter,
    estimate_footprint,
    verify_bundle,
)

from chimeraforge.weightspace import stage_bundle, verify_recipient as predict_recipient

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


@weightspace_app.command()
def admit_adapter(
    base: Path,
    adapter_dir: Path,
    base_repo: str = typer.Option(...),
    base_revision: str = typer.Option(...),
    base_sha256: str = typer.Option(...),
) -> None:
    """Admit a standard linear LoRA pair against immutable local base weights."""
    try:
        result = check_adapter(
            base,
            adapter_dir,
            base_repo=base_repo,
            base_revision=base_revision,
            base_sha256=base_sha256,
        )
    except ManifestError as exc:
        typer.echo(json.dumps({"status": "invalid", "error": str(exc)}))
        raise typer.Exit(1) from exc
    typer.echo(json.dumps(result.to_dict()))


@weightspace_app.command()
def stage(
    manifest: Path,
    destination: Path,
    root: Path | None = typer.Option(None),
    expected_sha256: str | None = typer.Option(None),
) -> None:
    """Stage the local runtime closure and atomically select the verified generation."""
    try:
        result = stage_bundle(manifest, destination, root, expected_sha256=expected_sha256)
    except ManifestError as exc:
        typer.echo(json.dumps({"status": "invalid", "error": str(exc)}))
        raise typer.Exit(1) from exc
    typer.echo(json.dumps(result.to_dict()))


@weightspace_app.command()
def verify_recipient(
    manifest: Path,
    text: str = typer.Option(...),
    root: Path | None = typer.Option(None),
    expected_sha256: str | None = typer.Option(None),
) -> None:
    """Run a standalone linear recipient on raw text in a fresh CPU worker."""
    try:
        result = predict_recipient(manifest, text, root, expected_sha256=expected_sha256)
    except ManifestError as exc:
        typer.echo(json.dumps({"status": "invalid", "error": str(exc)}))
        raise typer.Exit(1) from exc
    typer.echo(json.dumps(result.to_dict()))
