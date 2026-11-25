"""`catalog` command - build and inspect the local model catalog.

The catalog is a persisted set of resolved ModelSpecs (params + architecture)
covering a curated seed of popular models plus, optionally, the models installed
in a local Ollama. Once built, ``suggest --source catalog`` ranks them offline.
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

console = Console()
# Diagnostics go here so `--json` output on stdout stays exactly one document.
err_console = Console(stderr=True)


def catalog(
    build: bool = typer.Option(
        False, "--build", help="(Re)resolve the catalog's models and cache them."
    ),
    include_ollama: bool = typer.Option(
        False, "--with-ollama", help="Also include models installed in local Ollama."
    ),
    ollama_url: str = typer.Option(None, "--ollama-url", help="Ollama base URL."),
    hf_token: str = typer.Option(
        None, "--hf-token", help="HF token for gated repos (else $HF_TOKEN)."
    ),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging."),
) -> None:
    """Show the local model catalog, or rebuild it with --build.

    Without --build this lists what is already cached. --build resolves the
    bundled curated seed (and, with --with-ollama, your installed models) against
    the live HF/Ollama metadata APIs and persists the result so
    'suggest --source catalog' works offline afterwards.
    """
    import json as json_mod
    import logging

    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.WARNING,
        format="%(asctime)s %(name)s %(levelname)s  %(message)s",
    )

    from chimeraforge.planner.discovery import CatalogBuildError, build_catalog, load_catalog
    from chimeraforge.planner.resolver import ResolverError

    errors: list[tuple[str, str]] = []
    build_status = None
    if build:
        try:
            with err_console.status("Building catalog (resolving models)..."):
                specs, errors = build_catalog(
                    include_seed=True,
                    include_ollama=include_ollama,
                    ollama_url=ollama_url,
                    hf_token=hf_token,
                )
        except (CatalogBuildError, ResolverError) as exc:
            message = (
                str(exc)
                if isinstance(exc, CatalogBuildError)
                else "catalog source discovery failed"
            )
            specs, errors = {}, [("catalog", message)]
        if not specs:
            build_status = "failed"
            errors = errors or [("catalog", "no models were resolved")]
        else:
            build_status = "partial" if errors else "complete"
    else:
        specs = load_catalog()

    if output_json:
        out: dict[str, object] = {
            "models": {k: v.to_dict() for k, v in specs.items()},
            "errors": [{"id": i, "error": m} for i, m in errors],
        }
        if build_status is not None:
            out["status"] = build_status
        typer.echo(json_mod.dumps(out, indent=2))
        if build_status == "failed":
            raise typer.Exit(code=1)
        if not specs:
            err_console.print(
                "Catalog is empty. Run `chimeraforge catalog --build` to populate it."
            )
        return

    if build_status == "failed":
        err_console.print(f"Catalog refresh failed. {errors[0][1]}", markup=False)
        raise typer.Exit(code=1)
    if not specs:
        console.print(
            "[yellow]Catalog is empty.[/] Run [bold]chimeraforge catalog --build[/] to populate it."
        )
        return
    if build_status is not None:
        console.print(f"Catalog refresh {build_status}. Published {len(specs)} resolved models.")

    table = Table(title=f"Model catalog ({len(specs)} models)")
    table.add_column("Model")
    table.add_column("Src", style="dim")
    table.add_column("Params", justify="right")
    table.add_column("Layers", justify="right")
    table.add_column("KV", justify="right")
    table.add_column("d_head", justify="right")
    table.add_column("Family")
    for name, s in sorted(specs.items(), key=lambda kv: kv[1].params_b):
        table.add_row(
            name,
            s.source,
            f"{s.params_b}B",
            str(s.n_layers),
            str(s.n_kv_heads),
            str(s.d_head),
            s.family or "-",
        )
    console.print(table)
    if errors:
        console.print(f"  [yellow]{len(errors)} unresolved[/] (run with --verbose for details)")
