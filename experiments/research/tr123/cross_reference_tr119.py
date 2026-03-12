#!/usr/bin/env python3
"""
TR123: Cross-reference with TR119 uncached results.

Compares TR123 KV-cached $/tok against TR119 uncached $/tok to quantify
the production cost improvement from enabling KV-cache.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _find_tr119_results() -> Path | None:
    """Locate the most recent TR119 results JSONL."""
    tr119_dir = Path(__file__).resolve().parents[1] / "tr119" / "results"
    if not tr119_dir.exists():
        return None

    # Find the latest results directory or JSONL file
    jsonl_files = list(tr119_dir.rglob("*.jsonl"))
    if not jsonl_files:
        # Try CSV as fallback (TR119 may use CSV)
        csv_files = list(tr119_dir.rglob("*.csv"))
        return max(csv_files, key=lambda p: p.stat().st_mtime) if csv_files else None
    return max(jsonl_files, key=lambda p: p.stat().st_mtime)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _load_csv(path: Path) -> list[dict[str, Any]]:
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def load_tr119_results(path: Path | None = None) -> list[dict[str, Any]]:
    """Load TR119 results from either JSONL or CSV."""
    if path is None:
        path = _find_tr119_results()
    if path is None:
        logger.warning("No TR119 results found")
        return []

    if path.suffix == ".jsonl":
        return _load_jsonl(path)
    if path.suffix == ".csv":
        return _load_csv(path)
    logger.warning(f"Unknown file format: {path}")
    return []


def load_tr123_summary(results_dir: Path) -> list[dict[str, Any]]:
    """Load TR123 aggregated summary stats."""
    summary_path = results_dir / "summary_stats.csv"
    if not summary_path.exists():
        logger.warning(f"No summary_stats.csv found in {results_dir}")
        return []
    return _load_csv(summary_path)


def compute_improvement_ratios(
    tr119_rows: list[dict[str, Any]],
    tr123_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Match on (model, backend, scenario) and compute improvement ratios."""
    # Build TR119 lookup by (model, backend, scenario)
    tr119_lookup: dict[tuple, dict] = {}
    for row in tr119_rows:
        key = (
            row.get("model", ""),
            row.get("backend", ""),
            row.get("scenario", ""),
        )
        # Use total latency or cost if available
        tr119_lookup[key] = row

    comparisons = []
    for row in tr123_rows:
        key = (
            row.get("model", ""),
            row.get("backend", ""),
            row.get("scenario", ""),
        )

        tr119_match = tr119_lookup.get(key)
        if not tr119_match:
            continue

        # Extract comparable metrics
        # TR119 used uncached mode: total_ms is the relevant timing
        uncached_ms = _safe_float(
            tr119_match.get("latency_ms")
            or tr119_match.get("total_ms_mean")
            or tr119_match.get("total_ms")
        )
        cached_ms = _safe_float(row.get("total_ms_mean") or row.get("total_ms"))

        uncached_cost = _safe_float(
            tr119_match.get("cost_per_1m_tokens")
            or tr119_match.get("total_cost_usd_per_1m_tokens")
        )
        cached_cost = _safe_float(row.get("production_cost_per_1m_mean"))

        comparison = {
            "model": key[0],
            "backend": key[1],
            "scenario": key[2],
            "tr119_uncached_ms": uncached_ms,
            "tr123_cached_ms": cached_ms,
            "latency_speedup_x": (
                round(uncached_ms / cached_ms, 2)
                if uncached_ms and cached_ms and cached_ms > 0
                else None
            ),
            "tr119_uncached_cost_per_1m": uncached_cost,
            "tr123_cached_cost_per_1m": cached_cost,
            "cost_reduction_x": (
                round(uncached_cost / cached_cost, 2)
                if uncached_cost and cached_cost and cached_cost > 0
                else None
            ),
        }

        # Energy comparison if available
        tr119_energy = _safe_float(tr119_match.get("energy_j_per_tok"))
        tr123_energy_prefill = _safe_float(row.get("prefill_j_per_tok_mean"))
        tr123_energy_decode = _safe_float(row.get("decode_j_per_tok_mean"))
        if (
            tr119_energy
            and tr123_energy_prefill is not None
            and tr123_energy_decode is not None
        ):
            total_cached_energy = tr123_energy_prefill + tr123_energy_decode
            comparison["tr119_energy_j_per_tok"] = tr119_energy
            comparison["tr123_energy_j_per_tok"] = round(total_cached_energy, 6)
            comparison["energy_reduction_pct"] = (
                round((1.0 - total_cached_energy / tr119_energy) * 100, 1)
                if tr119_energy > 0
                else None
            )

        comparisons.append(comparison)

    return comparisons


def _safe_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        val = float(v)
        if val != val:  # NaN check
            return None
        return val
    except (ValueError, TypeError):
        return None


def main(tr123_results_dir: str | Path, tr119_path: str | Path | None = None):
    """Run cross-reference analysis and write improvement ratios."""
    tr123_results_dir = Path(tr123_results_dir)

    tr119_rows = load_tr119_results(Path(tr119_path) if tr119_path else None)
    tr123_rows = load_tr123_summary(tr123_results_dir)

    if not tr119_rows:
        logger.warning("No TR119 data available for cross-reference. Skipping.")
        return
    if not tr123_rows:
        logger.warning("No TR123 summary data available. Run analyze_results.py first.")
        return

    comparisons = compute_improvement_ratios(tr119_rows, tr123_rows)

    if not comparisons:
        logger.warning(
            "No matching (model, backend, scenario) pairs found between TR119 and TR123"
        )
        return

    output_path = tr123_results_dir / "improvement_ratios.csv"
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=comparisons[0].keys())
        w.writeheader()
        w.writerows(comparisons)

    logger.info(f"Wrote {len(comparisons)} comparisons → {output_path}")

    # Print summary
    speedups = [
        c["latency_speedup_x"] for c in comparisons if c.get("latency_speedup_x")
    ]
    cost_reductions = [
        c["cost_reduction_x"] for c in comparisons if c.get("cost_reduction_x")
    ]

    if speedups:
        import statistics

        logger.info(
            f"  Latency speedup: {statistics.mean(speedups):.1f}x mean, "
            f"{statistics.median(speedups):.1f}x median"
        )
    if cost_reductions:
        import statistics

        logger.info(
            f"  Cost reduction: {statistics.mean(cost_reductions):.1f}x mean, "
            f"{statistics.median(cost_reductions):.1f}x median"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TR123: Cross-Reference with TR119")
    parser.add_argument("results_dir", help="TR123 results directory")
    parser.add_argument("--tr119", default=None, help="Path to TR119 results")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    main(args.results_dir, args.tr119)
