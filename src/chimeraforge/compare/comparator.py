"""Compare benchmark result files — load, match, delta, format.

Loads two or more bench result JSON files, matches configurations by
(model, backend, quant, workload, context_length), computes deltas,
and outputs a Rich table or JSON summary.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------


def load_results(paths: list[Path]) -> list[dict]:
    """Load bench JSON files.

    Each file is expected to be a JSON array of result dicts.
    """
    all_results: list[dict] = []
    for p in paths:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            all_results.extend(data)
        else:
            all_results.append(data)
    return all_results


# ---------------------------------------------------------------------------
# Key / group
# ---------------------------------------------------------------------------


def make_key(result: dict) -> str:
    """Create comparison key from a result dict.

    Format: ``'{model}|{backend}|{quant}|{workload}|{context_length}'``.
    Uses ``'default'`` when quant is ``None``.
    """
    model = result.get("model", "")
    backend = result.get("backend", "")
    quant = result.get("quant") or "default"
    workload = result.get("workload", "single")
    ctx = result.get("context_length", 2048)
    return f"{model}|{backend}|{quant}|{workload}|{ctx}"


def group_by_key(results: list[dict]) -> dict[str, list[dict]]:
    """Group results by their comparison key."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        groups[make_key(r)].append(r)
    return groups


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class ComparisonRow:
    """One row in comparison output."""

    key: str
    model: str
    backend: str
    quant: str
    workload: str
    context_length: int
    # Baseline (first file)
    baseline_throughput: float
    baseline_ttft: float
    baseline_duration: float
    baseline_runs: int
    # Candidate (second file)
    candidate_throughput: float
    candidate_ttft: float
    candidate_duration: float
    candidate_runs: int
    # Deltas
    delta_throughput_pct: float
    delta_ttft_pct: float
    delta_duration_pct: float


# ---------------------------------------------------------------------------
# Compare
# ---------------------------------------------------------------------------


def _safe_delta_pct(base: float, cand: float) -> float:
    """Percentage change, guarded against division by zero."""
    if base == 0:
        return 0.0
    return (cand - base) / base * 100


def _extract_metrics(result: dict) -> tuple[float, float, float, int]:
    """Pull throughput, ttft, duration, and run count from a result dict."""
    agg = result.get("aggregate", {})
    throughput = agg.get("throughput_tps", {}).get("mean", 0.0)
    ttft = agg.get("ttft_ms", {}).get("mean", 0.0)
    duration = agg.get("total_duration_ms", {}).get("mean", 0.0)
    count = agg.get("count", 0)
    return throughput, ttft, duration, count


def compare_results(
    baseline_path: Path,
    candidate_paths: list[Path],
) -> list[ComparisonRow]:
    """Compare baseline against one or more candidate result files.

    Matches by ``(model, backend, quant, workload, context_length)``.
    Returns :class:`ComparisonRow` for matched configs only.
    """
    base_results = load_results([baseline_path])
    cand_results = load_results(candidate_paths)

    base_by_key = group_by_key(base_results)
    cand_by_key = group_by_key(cand_results)

    rows: list[ComparisonRow] = []
    for key, base_list in base_by_key.items():
        if key not in cand_by_key:
            continue
        cand_list = cand_by_key[key]

        # Use first result in each group
        base = base_list[0]
        cand = cand_list[0]

        b_tp, b_ttft, b_dur, b_runs = _extract_metrics(base)
        c_tp, c_ttft, c_dur, c_runs = _extract_metrics(cand)

        parts = key.split("|")
        rows.append(
            ComparisonRow(
                key=key,
                model=parts[0] if len(parts) > 0 else "",
                backend=parts[1] if len(parts) > 1 else "",
                quant=parts[2] if len(parts) > 2 else "default",
                workload=parts[3] if len(parts) > 3 else "single",
                context_length=int(parts[4]) if len(parts) > 4 else 2048,
                baseline_throughput=b_tp,
                baseline_ttft=b_ttft,
                baseline_duration=b_dur,
                baseline_runs=b_runs,
                candidate_throughput=c_tp,
                candidate_ttft=c_ttft,
                candidate_duration=c_dur,
                candidate_runs=c_runs,
                delta_throughput_pct=_safe_delta_pct(b_tp, c_tp),
                delta_ttft_pct=_safe_delta_pct(b_ttft, c_ttft),
                delta_duration_pct=_safe_delta_pct(b_dur, c_dur),
            )
        )

    return rows


# ---------------------------------------------------------------------------
# Format
# ---------------------------------------------------------------------------


def _delta_style(value: float, higher_is_better: bool = True) -> str:
    """Return a Rich-formatted delta string with colour."""
    sign = "+" if value >= 0 else ""
    if higher_is_better:
        colour = "green" if value > 0 else ("red" if value < 0 else "dim")
    else:
        colour = "red" if value > 0 else ("green" if value < 0 else "dim")
    return f"[{colour}]{sign}{value:.1f}%[/{colour}]"


def format_comparison_table(rows: list[ComparisonRow], console: Console) -> None:
    """Print Rich comparison table.

    Columns: Config | Base tok/s | Cand tok/s | delta% |
    Base TTFT | Cand TTFT | delta% | Base Dur | Cand Dur | delta%.
    Green for improvements, red for regressions.
    """
    if not rows:
        console.print("[dim]No matching configurations found.[/dim]")
        return

    table = Table(title="Benchmark Comparison", show_header=True, header_style="bold cyan")
    table.add_column("Config", style="bold", max_width=40)
    table.add_column("Base tok/s", justify="right")
    table.add_column("Cand tok/s", justify="right")
    table.add_column("delta", justify="right")
    table.add_column("Base TTFT", justify="right")
    table.add_column("Cand TTFT", justify="right")
    table.add_column("delta", justify="right")
    table.add_column("Base Dur", justify="right")
    table.add_column("Cand Dur", justify="right")
    table.add_column("delta", justify="right")

    for row in rows:
        label = f"{row.model}|{row.quant}"
        table.add_row(
            label,
            f"{row.baseline_throughput:.1f}",
            f"{row.candidate_throughput:.1f}",
            _delta_style(row.delta_throughput_pct, higher_is_better=True),
            f"{row.baseline_ttft:.1f}",
            f"{row.candidate_ttft:.1f}",
            _delta_style(row.delta_ttft_pct, higher_is_better=False),
            f"{row.baseline_duration:.1f}",
            f"{row.candidate_duration:.1f}",
            _delta_style(row.delta_duration_pct, higher_is_better=False),
        )

    console.print(table)


def format_comparison_json(rows: list[ComparisonRow]) -> str:
    """Serialize comparison rows to JSON."""
    data = []
    for row in rows:
        data.append(
            {
                "key": row.key,
                "model": row.model,
                "backend": row.backend,
                "quant": row.quant,
                "workload": row.workload,
                "context_length": row.context_length,
                "baseline_throughput": row.baseline_throughput,
                "baseline_ttft": row.baseline_ttft,
                "baseline_duration": row.baseline_duration,
                "baseline_runs": row.baseline_runs,
                "candidate_throughput": row.candidate_throughput,
                "candidate_ttft": row.candidate_ttft,
                "candidate_duration": row.candidate_duration,
                "candidate_runs": row.candidate_runs,
                "delta_throughput_pct": row.delta_throughput_pct,
                "delta_ttft_pct": row.delta_ttft_pct,
                "delta_duration_pct": row.delta_duration_pct,
            }
        )
    return json.dumps(data, indent=2)


def format_comparison_summary(rows: list[ComparisonRow], console: Console) -> None:
    """Print summary panel with aggregate statistics."""
    if not rows:
        console.print("[dim]No matching configurations to summarise.[/dim]")
        return

    n = len(rows)
    avg_tp = sum(r.delta_throughput_pct for r in rows) / n
    avg_dur = sum(r.delta_duration_pct for r in rows) / n
    improvements = sum(1 for r in rows if r.delta_throughput_pct > 0)
    regressions = sum(1 for r in rows if r.delta_throughput_pct < 0)

    lines = [
        f"Configs compared: {n}",
        f"Avg throughput delta: {_delta_style(avg_tp)}",
        f"Avg duration delta:  {_delta_style(avg_dur, higher_is_better=False)}",
        f"Improvements: [green]{improvements}[/green]  |  Regressions: [red]{regressions}[/red]",
    ]
    console.print(Panel("\n".join(lines), title="Summary", border_style="blue"))
