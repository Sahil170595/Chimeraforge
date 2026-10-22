"""`contribute` command - export, verify and quarantine contributed bench results."""

from __future__ import annotations

import json as json_mod
from pathlib import Path
from typing import NoReturn, TYPE_CHECKING

if TYPE_CHECKING:
    from chimeraforge.contribution_review import ContributionReceipt
    from chimeraforge.signed_contribution import SignedContribution

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
def verify(
    files: list[Path] = typer.Argument(..., help="Contribution files."),
    format: str = typer.Option(
        "auto", "--format", help="auto, v1 or v2; explicit v2 gives strict errors."
    ),
    trusted_key: list[Path] | None = typer.Option(
        None, "--trusted-key", help="Explicit trusted Ed25519 public PEM/raw32; repeat."
    ),
    out: Path | None = typer.Option(
        None, "--out", help="Atomic verification receipt; protects all inputs."
    ),
    output_json: bool = typer.Option(False, "--json"),
) -> None:
    """Check each file's schema and content hash."""
    from chimeraforge.contrib import ContribError, verify_contribution

    reports, codes = [], []
    keys = tuple(trusted_key or ())
    if format not in ("auto", "v1", "v2"):
        _signed_fail("format must be auto, v1 or v2", output_json, 2)
    if out is not None:
        _preprotect(out, (*files, *keys), output_json)
    for path in files:
        try:
            data, paths = _exchange(path, format)
        except ContribError as exc:
            if format != "v2" and not output_json and not keys:
                _fail(f"{escape(str(path))}: {escape(str(exc))}")
            _signed_fail("malformed contribution input", output_json, 2)
        version = 2 if format == "v2" or format == "auto" and data.get("schema_version") == 2 else 1
        if version == 1:
            try:
                verify_contribution(data)
            except ContribError as exc:
                if output_json or keys:
                    _signed_fail("malformed v1 contribution input", output_json, 2)
                _fail(f"{escape(str(path))}: {escape(str(exc))}")
            reports.append(
                {
                    "schema_version": 1,
                    "status": "verified_unsigned_v1",
                    "exit_code": 0,
                    "id": data["id"],
                    "producer_authentication": "unverified",
                }
            )
            codes.append(0)
            if not output_json:
                console.print(f"[green]ok[/] {escape(str(path))}")
        else:
            from chimeraforge.api import verify_signed_contribution
            from chimeraforge.signed_contribution import SignedContribution

            try:
                receipt = verify_signed_contribution(
                    SignedContribution(data, paths), trusted_keys=keys
                )
            except ContribError:
                _signed_fail("malformed signed contribution or trusted key", output_json, 2)
            reports.append(receipt.to_dict())
            codes.append(receipt.exit_code)
            if not output_json:
                typer.echo(receipt.to_dict()["status"] + ": " + receipt.to_dict()["trust"]["state"])
    code = next((value for value in (2, 1, 3) if value in codes), 0)
    if output_json or out is not None:
        from chimeraforge.signed_contribution import SignedContributionReceipt
        from chimeraforge.signed_payload import hash_json

        report = (
            reports[0]
            if len(reports) == 1
            else {
                "kind": "chimeraforge.contribution-verification-batch",
                "results": reports,
                "exit_code": code,
                "status": "completed" if code == 0 else "unqualified",
            }
        )
        if len(reports) != 1:
            report["fingerprint"] = hash_json(report)
        receipt = SignedContributionReceipt(report, (*files, *keys))
        if out is not None:
            _save_signed(receipt, out, output_json)
        if output_json:
            typer.echo(json_mod.dumps(report, allow_nan=False))
    raise typer.Exit(code)


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


def _print_receipt(
    receipt: ContributionReceipt | SignedContribution, output_json: bool, out: Path | None
) -> None:
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
    prompt: str | None = typer.Option(
        None, help="v1 explicit prompt sent to the endpoint; receipt stores its hash."
    ),
    output_tokens: int | None = typer.Option(
        None, help="v1 applied output-token cap, not guaranteed returned length."
    ),
    runs: int | None = typer.Option(
        None, help="v1 replay count, defaults5; v2 uses recorded count."
    ),
    format: str = typer.Option("auto", "--format", help="auto, v1 or v2."),
    private_workload: Path | None = typer.Option(
        None, "--private-workload", help="v2 private JSON with exact prompt/options bindings."
    ),
    trusted_key: list[Path] | None = typer.Option(
        None, "--trusted-key", help="Explicit trusted Ed25519 public PEM/raw32; repeat."
    ),
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
        if format not in ("auto", "v1", "v2"):
            raise ContribError("format must be auto, v1 or v2")
        data, paths = _exchange(source, format)
        keys = tuple(trusted_key or ())
        if out is not None:
            _preprotect(
                out, paths + keys + ((private_workload,) if private_workload else ()), output_json
            )
        if format == "v2" or format == "auto" and data.get("schema_version") == 2:
            from chimeraforge.api import replay_signed_contribution
            from chimeraforge.signed_contribution import SignedContribution

            if private_workload is None or any(
                value is not None
                for value in (
                    prompt,
                    output_tokens,
                    runs,
                    model,
                    backend,
                    workload,
                    rate,
                    concurrency,
                )
            ):
                raise ContribError(
                    "v2 replay uses private-workload and recorded controls; no v1 overrides"
                )
            report = asyncio.run(
                replay_signed_contribution(
                    SignedContribution(data, paths),
                    private_workload,
                    trusted_keys=keys,
                    base_url=base_url,
                )
            )
            _print_signed(report, output_json, out)
            return
        if prompt is None or output_tokens is None or private_workload is not None or keys:
            raise ContribError(
                "v1 replay requires prompt/output-tokens and cannot accept v2 bindings"
            )
        if out is not None:
            review_contribution(data).check_output(out)
        report = asyncio.run(
            replay_contribution(
                data,
                prompt=prompt,
                output_tokens=output_tokens,
                runs=runs if runs is not None else 5,
                model=model,
                backend=backend,
                base_url=base_url,
                workload=workload,
                rate=rate,
                concurrency=concurrency,
            )
        )
    except ContribError as exc:
        if output_json or format == "v2" or private_workload is not None or trusted_key:
            _signed_fail("malformed contribution replay input or private bindings", output_json, 2)
        err_console.print(f"[red]Error:[/] {escape(str(exc))}")
        raise typer.Exit(code=2)
    from chimeraforge.signed_contribution import SignedContributionReceipt

    _print_receipt(SignedContributionReceipt(report.to_dict(), paths), output_json, out)


def _signed_fail(message: str, output_json: bool, code: int) -> NoReturn:
    typer.echo(json_mod.dumps({"error": message}) if output_json else message)
    raise typer.Exit(code)


def _exchange(source: str | Path, format: str) -> tuple[dict, tuple[Path, ...]]:
    from chimeraforge.contrib import quarantine_dir
    from chimeraforge.signed_payload import MAX_ENVELOPE_BYTES, held_json

    if (
        format != "v2"
        and isinstance(source, str)
        and len(source) == 64
        and all(char in "0123456789abcdef" for char in source)
    ):
        source = quarantine_dir() / f"{source}.json"
    data, _, paths = held_json(source, MAX_ENVELOPE_BYTES)
    return data, paths


def _preprotect(out: Path, paths: tuple[Path, ...], output_json: bool) -> None:
    from chimeraforge.contrib import ContribError
    from chimeraforge.signed_contribution import check_output

    try:
        check_output(out, paths)
    except ContribError:
        _signed_fail(
            "output cannot replace a consumed input/key/artifact or quarantine", output_json, 2
        )


def _save_signed(receipt: SignedContribution, out: Path, output_json: bool) -> None:
    from chimeraforge.contrib import ContribError

    try:
        receipt.save(out)
    except ContribError:
        _signed_fail("signed contribution output failed", output_json, 2)


def _print_signed(receipt: SignedContribution, output_json: bool, out: Path | None) -> None:
    if out is not None:
        _save_signed(receipt, out, output_json)
    data = receipt.to_dict()
    typer.echo(
        json_mod.dumps(data, allow_nan=False)
        if output_json
        else (
            data.get("status", "signed")
            + ": signed contribution operation; measurement truth unverified"
        )
    )
    raise typer.Exit(receipt.exit_code)


@contribute_app.command("gate")
def gate_cmd(
    baseline: list[Path] = typer.Option(
        ..., "--baseline", help="Ordered signed v2 baseline; repeat."
    ),
    candidate: list[Path] = typer.Option(
        ..., "--candidate", help="Ordered signed v2 candidate; repeat."
    ),
    policy: Path = typer.Option(..., "--policy", help="Explicit native regression policy JSON."),
    trusted_key: list[Path] | None = typer.Option(
        None, "--trusted-key", help="Receiver-trusted Ed25519 public PEM/raw32; repeat."
    ),
    out: Path | None = typer.Option(
        None, "--out", help="Decision outside consumed inputs and quarantine."
    ),
    output_json: bool = typer.Option(False, "--json"),
) -> None:
    """Compare trusted native facts offline; signatures do not prove measurement truth."""
    from chimeraforge.api import gate_signed_contributions
    from chimeraforge.contrib import ContribError
    from chimeraforge.signed_contribution import SigningUnavailable

    keys = tuple(trusted_key or ())
    if out is not None:
        _preprotect(out, (*baseline, *candidate, policy, *keys), output_json)
    try:
        decision = gate_signed_contributions(baseline, candidate, trusted_keys=keys, policy=policy)
    except SigningUnavailable:
        _signed_fail("signed gate requires available Ed25519 support", output_json, 3)
    except ContribError:
        _signed_fail("invalid signed gate input, policy or trusted key", output_json, 2)
    _print_signed(decision, output_json, out)


@contribute_app.command("sign")
def sign_cmd(
    receipt: Path = typer.Argument(..., help="Current validated PlanBenchmark receipt."),
    private_key: Path = typer.Option(
        ..., "--private-key", help="Ed25519 unencrypted PKCS8 PEM/raw32 seed."
    ),
    out: Path = typer.Option(
        ..., "--out", help="Atomic signed artifact, outside planner quarantine."
    ),
    output_json: bool = typer.Option(False, "--json"),
) -> None:
    """Sign public native facts/private commitments without proving measurement truth."""
    from chimeraforge.api import sign_contribution
    from chimeraforge.contrib import ContribError
    from chimeraforge.signed_contribution import SigningUnavailable

    _preprotect(out, (receipt, private_key), output_json)
    try:
        signed = sign_contribution(receipt, private_key)
    except SigningUnavailable as exc:
        _signed_fail(str(exc), output_json, 3)
    except ContribError:
        _signed_fail("invalid current benchmark receipt or Ed25519 private key", output_json, 2)
    _print_signed(signed, output_json, out)
