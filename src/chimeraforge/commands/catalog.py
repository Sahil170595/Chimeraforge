"""`catalog` command — build and inspect the local model catalog.

The catalog is a persisted set of resolved ModelSpecs (params + architecture)
covering a curated seed of popular models plus, optionally, the models installed
in a local Ollama. Once built, ``suggest --source catalog`` ranks them offline.
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

console = Console()


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

    from chimeraforge.planner.discovery import build_catalog, load_catalog

    errors: list[tuple[str, str]] = []
    if build:
        with console.status("Building catalog (resolving models)..."):
            specs, errors = build_catalog(
                include_seed=True,
                include_ollama=include_ollama,
                ollama_url=ollama_url,
                hf_token=hf_token,
            )
        console.print(
            f"[green]Built catalog:[/] {len(specs)} models resolved, {len(errors)} failed."
        )
    else:
        specs = load_catalog()
        if not specs:
            console.print(
                "[yellow]Catalog is empty.[/] Run [bold]chimeraforge catalog --build[/] "
                "to populate it."
            )
            raise typer.Exit(code=0)

    if output_json:
        out = {
            "models": {k: v.to_dict() for k, v in specs.items()},
            "errors": [{"id": i, "error": m} for i, m in errors],
        }
        console.print(json_mod.dumps(out, indent=2), highlight=False, soft_wrap=True)
        return

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
