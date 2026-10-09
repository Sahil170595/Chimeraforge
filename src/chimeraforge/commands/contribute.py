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
    from chimeraforge.contrib import ContribError, build_contribution, read_json_file

    out.mkdir(parents=True, exist_ok=True)
    for path in bench_files:
        try:
            data = read_json_file(path)
        except ContribError as exc:
            _fail(escape(str(exc)))
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
    from chimeraforge.contrib import ContribError, read_json_file, verify_contribution

    for path in files:
        try:
            verify_contribution(read_json_file(path))
        except ContribError as exc:
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


def _print_receipt(receipt, output_json: bool, out: Path | None) -> None:
    from chimeraforge.contrib import ContribError

    if out is not None:
        try:
            receipt.save(out)
        except (ContribError, OSError) as exc:
            err_console.print(f"[red]Error:[/] {escape(str(exc))}")
            raise typer.Exit(code=2)
    data = receipt.to_dict()
    if output_json:
        console.print(
            json_mod.dumps(data, indent=2, allow_nan=False), highlight=False, soft_wrap=True
        )
    else:
        console.print(
            f"{data['status']}: unsigned contribution {data['contribution']['id'][:ID_PREFIX_LEN]}"
        )
        console.print(
            "Replay equivalence and producer authenticity remain unverified; "
            "quarantine is unchanged."
        )
        if "decision" in data:
            console.print(f"Disposition: {data['decision']['disposition']} (review receipt only).")
        if "gpu_eligibility" in data:
            console.print(f"GPU eligibility: {data['gpu_eligibility']['state']}")
            metric = data["comparison"]["decode_tps"]
            console.print(
                f"Decode tok/s: declared {metric['original']}, replayed {metric['replayed']}; "
                "arithmetic only."
            )
    raise typer.Exit(code=receipt.exit_code)


@contribute_app.command("review")
def review_cmd(
    source: str = typer.Argument(..., help="Contribution file or full quarantined id."),
    decision: str = typer.Option(
        "pending", help="pending, retain or reject; never changes quarantine/trust."
    ),
    reason: str | None = typer.Option(
        None, help="Unsigned review rationale; required for retain/reject."
    ),
    out: Path | None = typer.Option(None, help="Atomic review receipt destination."),
    output_json: bool = typer.Option(False, "--json", help="Print the complete receipt as JSON."),
) -> None:
    """Inspect unsigned evidence and record a disposition without importing/promoting it."""
    from chimeraforge.api import review_contribution
    from chimeraforge.contrib import ContribError

    try:
        report = review_contribution(source, decision=decision, reason=reason)
        if out is not None:
            report.check_output(out)
    except ContribError as exc:
        err_console.print(f"[red]Error:[/] {escape(str(exc))}")
        raise typer.Exit(code=2)
    _print_receipt(report, output_json, out)


@contribute_app.command("replay")
def replay_cmd(
    source: str = typer.Argument(..., help="Contribution file or full quarantined id."),
    prompt: str = typer.Option(
        ..., help="Explicit prompt sent to the endpoint; receipt stores its hash."
    ),
    output_tokens: int = typer.Option(
        ..., help="Applied output-token cap, not guaranteed returned length."
    ),
    runs: int = typer.Option(5, help="Replay request count (1-1000)."),
    model: str | None = typer.Option(
        None, help="Explicit served model override; differences stay visible."
    ),
    backend: str | None = typer.Option(None, help="Serving adapter override."),
    base_url: str | None = typer.Option(
        None, help="Serving endpoint; persisted URL omits credentials/query."
    ),
    workload: str | None = typer.Option(
        None, help="single, batch or server; defaults to the declared profile."
    ),
    rate: float | None = typer.Option(
        None, help="Explicit server-workload Poisson arrival-rate parameter."
    ),
    concurrency: int | None = typer.Option(None, help="Applied batch/server concurrency."),
    out: Path | None = typer.Option(None, help="Atomic replay receipt destination."),
    output_json: bool = typer.Option(False, "--json", help="Print the complete receipt as JSON."),
) -> None:
    """Execute a live probe and retain unknown legacy bindings and known mismatches."""
    import asyncio
    from chimeraforge.api import replay_contribution, review_contribution
    from chimeraforge.contrib import ContribError

    try:
        if out is not None:
            review_contribution(source).check_output(out)
        report = asyncio.run(
            replay_contribution(
                source,
                prompt=prompt,
                output_tokens=output_tokens,
                runs=runs,
                model=model,
                backend=backend,
                base_url=base_url,
                workload=workload,
                rate=rate,
                concurrency=concurrency,
            )
        )
    except ContribError as exc:
        err_console.print(f"[red]Error:[/] {escape(str(exc))}")
        raise typer.Exit(code=2)
    _print_receipt(report, output_json, out)
