"""Compare benchmark result files - load, match, delta, format.

Loads two or more bench result JSON files, matches configurations by
(model, backend, quant, workload, context_length), computes deltas,
and outputs a Rich table or JSON summary.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rich.console import Console


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
        results = data if isinstance(data, list) else [data]
        if any(not isinstance(row, dict) for row in results):
            raise ValueError(f"{p}: expected benchmark result objects")
        all_results.extend(results)
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
    baseline_throughput: float | None
    baseline_ttft: float | None
    baseline_duration: float | None
    baseline_runs: int
    # Candidate (second file)
    candidate_throughput: float | None
    candidate_ttft: float | None
    candidate_duration: float | None
    candidate_runs: int
    # Deltas
    # None when either observation is missing or the baseline cannot be divided.
    delta_throughput_pct: float | None
    delta_ttft_pct: float | None
    delta_duration_pct: float | None


@dataclass
class CandidateComparison:
    """One candidate file, with matched rows and each side's unmatched keys."""

    candidate: Path
    rows: list[ComparisonRow]
    baseline_only: list[str]
    candidate_only: list[str]


# ---------------------------------------------------------------------------
# Compare
# ---------------------------------------------------------------------------


def _ratio_delta_pct(base_total: float, cand_total: float) -> float | None:
    """Aggregate change as a ratio of totals, which is what a summary should be."""
    return _safe_delta_pct(base_total, cand_total)


def _safe_delta_pct(base: float | None, cand: float | None) -> float | None:
    """Calculate a percentage only for two usable observations and a positive baseline."""
    if base is None or cand is None or base <= 0 or cand < 0:
        return None
    if not math.isfinite(base) or not math.isfinite(cand):
        return None
    delta = (cand - base) / base * 100
    return delta if math.isfinite(delta) else None


def _metric(aggregate: dict, name: str) -> float | None:
    stats = aggregate.get(name)
    mean = stats.get("mean") if isinstance(stats, dict) else None
    if not isinstance(mean, (int, float)) or isinstance(mean, bool) or mean < 0:
        return None
    try:
        value = float(mean)
    except OverflowError:
        return None
    return value if math.isfinite(value) else None


def _extract_metrics(result: dict) -> tuple[float | None, float | None, float | None, int]:
    """Pull throughput, ttft, duration, and run count from a result dict."""
    agg = result.get("aggregate", {})
    if not isinstance(agg, dict):
        raise ValueError("expected a benchmark aggregate object")
    count = agg.get("count", 0)
    return (
        _metric(agg, "throughput_tps"),
        _metric(agg, "ttft_ms"),
        _metric(agg, "total_duration_ms"),
        count if type(count) is int and count >= 0 else 0,
    )


def _load_unique(path: Path) -> dict[str, dict]:
    groups = group_by_key(load_results([path]))
    for key, rows in groups.items():
        if key.count("|") != 4:
            raise ValueError(f"{path}: invalid comparison configuration {key!r}")
        if len(rows) != 1:
            raise ValueError(f"{path}: duplicate configuration {key!r}")
    return {key: rows[0] for key, rows in groups.items()}


def _compare_row(key: str, base: dict, cand: dict) -> ComparisonRow:
    b_tp, b_ttft, b_dur, b_runs = _extract_metrics(base)
    c_tp, c_ttft, c_dur, c_runs = _extract_metrics(cand)
    return ComparisonRow(
        key=key,
        model=str(base.get("model", "")),
        backend=str(base.get("backend", "")),
        quant=str(base.get("quant") or "default"),
        workload=str(base.get("workload", "single")),
        context_length=int(str(base.get("context_length", 2048))),
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


def compare_candidates(
    baseline_path: Path, candidate_paths: list[Path]
) -> list[CandidateComparison]:
    """Compare each candidate file independently in caller order."""
    baseline = _load_unique(baseline_path)
    comparisons = []
    for path in candidate_paths:
        candidate = _load_unique(path)
        comparisons.append(
            CandidateComparison(
                candidate=path,
                rows=[
                    _compare_row(key, base, candidate[key])
                    for key, base in baseline.items()
                    if key in candidate
                ],
                baseline_only=[key for key in baseline if key not in candidate],
                candidate_only=[key for key in candidate if key not in baseline],
            )
        )
    return comparisons


def compare_results(
    baseline_path: Path,
    candidate_paths: list[Path],
) -> list[ComparisonRow]:
    """Return matched rows in candidate-file order. Use compare_candidates for the census."""
    return [
        row for group in compare_candidates(baseline_path, candidate_paths) for row in group.rows
    ]


# ---------------------------------------------------------------------------
# Format
# ---------------------------------------------------------------------------


def _delta_style(value: float | None, higher_is_better: bool = True) -> str:
    """Return a Rich-formatted delta string with colour, or n/a when undefined."""
    if value is None:
        # Not 0.0%: an undefined comparison must not render as "no change".
        return "[dim]n/a[/dim]"
    sign = "+" if value >= 0 else ""
    if higher_is_better:
        colour = "green" if value > 0 else ("red" if value < 0 else "dim")
    else:
        colour = "red" if value > 0 else ("green" if value < 0 else "dim")
    return f"[{colour}]{sign}{value:.1f}%[/{colour}]"


def _metric_style(value: float | None) -> str:
    return "[dim]n/a[/dim]" if value is None else f"{value:.1f}"


def format_comparison_table(rows: list[ComparisonRow], console: Console) -> None:
    """Print Rich comparison table.

    Columns: Config | Base tok/s | Cand tok/s | delta% |
    Base TTFT | Cand TTFT | delta% | Base Dur | Cand Dur | delta%.
    Green for improvements, red for regressions.
    """
    from rich.table import Table

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
            _metric_style(row.baseline_throughput),
            _metric_style(row.candidate_throughput),
            _delta_style(row.delta_throughput_pct, higher_is_better=True),
            _metric_style(row.baseline_ttft),
            _metric_style(row.candidate_ttft),
            _delta_style(row.delta_ttft_pct, higher_is_better=False),
            _metric_style(row.baseline_duration),
            _metric_style(row.candidate_duration),
            _delta_style(row.delta_duration_pct, higher_is_better=False),
        )

    console.print(table)


def format_comparison_json(rows: list[ComparisonRow]) -> str:
    """Serialize comparison rows to JSON."""
    return json.dumps([asdict(row) for row in rows], indent=2, allow_nan=False)


def format_candidate_groups_json(baseline: Path, comparisons: list[CandidateComparison]) -> str:
    """Serialize the ordered multi-candidate comparison document."""
    return json.dumps(
        {
            "schema_version": 1,
            "baseline": str(baseline),
            "candidates": [
                {
                    "candidate": str(group.candidate),
                    "rows": [asdict(row) for row in group.rows],
                    "baseline_only": group.baseline_only,
                    "candidate_only": group.candidate_only,
                }
                for group in comparisons
            ],
        },
        indent=2,
        allow_nan=False,
    )


def _comparable_totals(
    pairs: Iterable[tuple[float | None, float | None]],
) -> tuple[float, float]:
    baseline = candidate = 0.0
    for before, after in pairs:
        if before is not None and after is not None and _safe_delta_pct(before, after) is not None:
            baseline += before
            candidate += after
    return baseline, candidate


def format_comparison_summary(rows: list[ComparisonRow], console: Console) -> None:
    """Print summary panel with aggregate statistics."""
    from rich.panel import Panel

    if not rows:
        console.print("[dim]No matching configurations to summarise.[/dim]")
        return

    n = len(rows)
    # Ratio of totals, not a mean of percentages. Averaging percentages is not a
    # meaningful aggregate: 100->50 paired with 50->100 is no net change, but the
    # mean of -50% and +100% reports +25% and renders it green.
    agg_tp = _ratio_delta_pct(
        *_comparable_totals((r.baseline_throughput, r.candidate_throughput) for r in rows)
    )
    agg_dur = _ratio_delta_pct(
        *_comparable_totals((r.baseline_duration, r.candidate_duration) for r in rows)
    )
    improvements = sum(1 for r in rows if (r.delta_throughput_pct or 0) > 0)
    regressions = sum(1 for r in rows if (r.delta_throughput_pct or 0) < 0)
    undefined = sum(1 for r in rows if r.delta_throughput_pct is None)

    lines = [
        f"Configs compared: {n}",
        f"Total throughput delta: {_delta_style(agg_tp)}",
        f"Total duration delta:  {_delta_style(agg_dur, higher_is_better=False)}",
        f"Improvements: [green]{improvements}[/green]  |  Regressions: [red]{regressions}[/red]",
    ]
    if undefined:
        lines.append(
            f"[yellow]{undefined} config(s) had undefined throughput deltas[/yellow] "
            "and are excluded from the throughput total."
        )
    console.print(Panel("\n".join(lines), title="Summary", border_style="blue"))
