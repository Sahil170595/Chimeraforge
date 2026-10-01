"""`contribute` command - export, verify and quarantine contributed bench results."""

from __future__ import annotations

import json as json_mod
from pathlib import Path

import typer
from rich.console import Console
from rich.markup import escape
from rich.table import Table

console = Console()
err_console = Console(stderr=True)

contribute_app = typer.Typer(
    help="Share bench results as fingerprinted contributions, and quarantine others'. "
    "Imported numbers are never blended into the bundled or measured corpus; "
    "`plan --contributions` uses them only when asked, labelled `contributed`.",
    no_args_is_help=True,
)

# Exported files are named by the start of their content id.
ID_PREFIX_LEN = 12


def _fail(message: str) -> None:
    err_console.print(f"[red]Error:[/] {message}")
    raise typer.Exit(code=1)


@contribute_app.command("export")
def export(
    bench_files: list[Path] = typer.Argument(
        ..., help="Result files `chimeraforge bench` saves (see --output-dir)."
    ),
    out: Path = typer.Option(
        Path("."), "--out", "-o", help="Directory for the contribution files."
    ),
) -> None:
    """Turn bench results into contribution files (one per result)."""
    from chimeraforge.contrib import ContribError, build_contribution

    out.mkdir(parents=True, exist_ok=True)
    for path in bench_files:
        try:
            data = json_mod.loads(path.read_text(encoding="utf-8"))
        except (OSError, json_mod.JSONDecodeError) as exc:
            _fail(f"could not read {escape(str(path))}: {exc}")
        for result in data if isinstance(data, list) else [data]:
            try:
                contribution = build_contribution(result)
            except ContribError as exc:
                _fail(f"{escape(str(path))}: {escape(str(exc))}")
            dest = out / f"{contribution['id'][:ID_PREFIX_LEN]}.contribution.json"
            dest.write_text(json_mod.dumps(contribution, indent=2) + "\n", encoding="utf-8")
            fp = contribution["fingerprint"]
            console.print(
                f"[green]wrote[/] {escape(str(dest))}: {escape(str(fp['model']))} | "
                f"{fp['backend']} | {fp['quant']} on {escape(str(fp['gpu_name']))}"
            )
            for flag in contribution["flags"]:
                console.print(f"  [yellow]flag:[/] {escape(flag)}")
    console.print(
        "[dim]Unsigned: the id proves the file is unaltered, not who ran it. "
        "Recipients import it into quarantine.[/]"
    )


@contribute_app.command("verify")
def verify(files: list[Path] = typer.Argument(..., help="Contribution files.")) -> None:
    """Check each file's schema and content hash."""
    from chimeraforge.contrib import ContribError, verify_contribution

    for path in files:
        try:
            verify_contribution(json_mod.loads(path.read_text(encoding="utf-8")))
        except (OSError, json_mod.JSONDecodeError, ContribError) as exc:
            _fail(f"{escape(str(path))}: {escape(str(exc))}")
        console.print(f"[green]ok[/] {escape(str(path))}")


@contribute_app.command("import")
def import_cmd(files: list[Path] = typer.Argument(..., help="Contribution files.")) -> None:
    """Verify contributions and add them to the local quarantine."""
    from chimeraforge.contrib import ContribError, import_contribution, quarantine_dir

    for path in files:
        try:
            cid, new = import_contribution(path)
        except ContribError as exc:
            _fail(escape(str(exc)))
        state = "added" if new else "already present"
        console.print(f"[green]{state}[/] {cid[:ID_PREFIX_LEN]} from {escape(str(path))}")
    console.print(f"[dim]Quarantine: {escape(str(quarantine_dir()))}[/]")


@contribute_app.command("list")
def list_cmd(output_json: bool = typer.Option(False, "--json", help="Print as JSON.")) -> None:
    """Show the quarantined contributions."""
    from chimeraforge.contrib import load_quarantine

    items = load_quarantine()
    if output_json:
        console.print(json_mod.dumps(items, indent=2), highlight=False, soft_wrap=True)
        return
    if not items:
        console.print("The quarantine is empty.")
        return
    table = Table(title="Quarantined contributions (unverified)")
    for col in ("id", "model", "engine", "quant", "GPU", "decode tok/s", "runs", "flags"):
        table.add_column(col)
    for c in items:
        fp, m = c["fingerprint"], c["measurements"]
        table.add_row(
            c["id"][:ID_PREFIX_LEN],
            escape(str(fp.get("model"))),
            f"{fp.get('backend')} {fp.get('backend_version') or ''}".strip(),
            str(fp.get("quant")),
            escape(str(fp.get("gpu_name"))),
            f"{m['decode_tps_mean']:.1f}",
            str(len(m["decode_tps"])),
            str(len(c.get("flags") or [])),
        )
    console.print(table)
