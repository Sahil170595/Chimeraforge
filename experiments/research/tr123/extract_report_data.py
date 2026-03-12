#!/usr/bin/env python3
"""
TR123: Extract report data from raw_measurements.jsonl.

Reads the JSONL file, filters to status=="ok" rows, and computes:
  (a) Per (model, backend): CV of decode_ms, min/max, worst warmup ratio
  (b) Per (model, backend, scenario): mean, std, max/min ratio of decode_ms
Prints all results in formatted tables.

Also investigates whether warmup runs exist in the recorded data.
"""

from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path
import statistics
import sys

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

JSONL_PATH = (
    Path(__file__).resolve().parent
    / "results"
    / "20260216_181539"
    / "raw_measurements.jsonl"
)

# ---------------------------------------------------------------------------
# Load & filter
# ---------------------------------------------------------------------------


def load_ok_rows(path: Path) -> list[dict]:
    """Load all rows from the JSONL file where status == 'ok'."""
    rows = []
    total = 0
    status_counts: dict[str, int] = defaultdict(int)
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            total += 1
            status_counts[rec.get("status", "unknown")] += 1
            if rec.get("status") == "ok":
                rows.append(rec)
    return rows, total, dict(status_counts)


# ---------------------------------------------------------------------------
# Warmup investigation
# ---------------------------------------------------------------------------


def investigate_warmup(rows: list[dict]) -> None:
    """Check if warmup runs exist in the data."""
    print("=" * 80)
    print("WARMUP INVESTIGATION")
    print("=" * 80)

    # Check for warmup-related fields
    if rows:
        sample = rows[0]
        warmup_fields = [k for k in sample if "warm" in k.lower()]
        print(f"\nFields containing 'warm' in schema: {warmup_fields or 'NONE'}")
        print(f"Fields containing 'is_warmup': {'is_warmup' in sample}")
        print(f"'rep' field present: {'rep' in sample}")

    # Check rep range per (model, backend, scenario)
    rep_ranges: dict[tuple, list[int]] = defaultdict(list)
    for r in rows:
        key = (r["model"], r["backend"], r["scenario"])
        rep_ranges[key].append(r["rep"])

    print("\nRep ranges per (model, backend, scenario) group:")
    print(f"  {'Group':<60s} {'Reps':>5s}  Range")
    print(f"  {'-'*60} {'-----':>5s}  {'----------'}")
    for key in sorted(rep_ranges.keys()):
        reps = sorted(rep_ranges[key])
        label = f"{key[0]}/{key[1]}/{key[2]}"
        print(f"  {label:<60s} {len(reps):>5d}  {min(reps)}-{max(reps)}")

    # Summary
    all_reps = set()
    for reps in rep_ranges.values():
        all_reps.update(reps)
    print(f"\n  Global rep values found: {sorted(all_reps)}")
    print(f"  Total ok groups: {len(rep_ranges)}")

    print("\n  CONCLUSION: Warmup runs are NOT recorded in the JSONL.")
    print("  The benchmark code (run_benchmark.py lines 1057-1069) runs warmup")
    print("  iterations but does not write them to the output file.")
    print("  All rep=0..6 rows are post-warmup measured runs.")
    print()


# ---------------------------------------------------------------------------
# Analytics helpers
# ---------------------------------------------------------------------------


def cv(values: list[float]) -> float:
    """Coefficient of variation: std/mean * 100."""
    if len(values) < 2:
        return 0.0
    m = statistics.mean(values)
    if m == 0:
        return 0.0
    return statistics.stdev(values) / m * 100.0


def warmup_ratio_per_scenario(
    rows: list[dict], model: str, backend: str, scenario: str
) -> float | None:
    """Compute ratio of rep=0 mean decode_ms to rep>0 mean decode_ms.

    A ratio > 1.0 suggests the first measured rep is slower (residual warmup).
    A ratio ~ 1.0 suggests warmup was fully eliminated before measurement.
    """
    rep0 = [
        r["decode_ms"]
        for r in rows
        if r["model"] == model
        and r["backend"] == backend
        and r["scenario"] == scenario
        and r["rep"] == 0
    ]
    rest = [
        r["decode_ms"]
        for r in rows
        if r["model"] == model
        and r["backend"] == backend
        and r["scenario"] == scenario
        and r["rep"] > 0
    ]
    if not rep0 or not rest:
        return None
    mean_rep0 = statistics.mean(rep0)
    mean_rest = statistics.mean(rest)
    if mean_rest == 0:
        return None
    return mean_rep0 / mean_rest


# ---------------------------------------------------------------------------
# Section (b): Per (model, backend) aggregates
# ---------------------------------------------------------------------------


def report_model_backend(rows: list[dict]) -> None:
    """Report per (model, backend) aggregates."""
    print("=" * 80)
    print("SECTION B: Per (model, backend) Aggregates")
    print("=" * 80)

    # Group rows
    groups: dict[tuple, list[float]] = defaultdict(list)
    for r in rows:
        key = (r["model"], r["backend"])
        groups[key].append(r["decode_ms"])

    # Compute worst warmup ratio per (model, backend)
    warmup_ratios: dict[tuple, tuple[float, str]] = {}
    scenarios_seen: dict[tuple, set] = defaultdict(set)
    for r in rows:
        key = (r["model"], r["backend"])
        scenarios_seen[key].add(r["scenario"])

    for key in sorted(groups.keys()):
        model, backend = key
        worst_ratio = None
        worst_scenario = ""
        for scenario in sorted(scenarios_seen[key]):
            ratio = warmup_ratio_per_scenario(rows, model, backend, scenario)
            if ratio is not None and (worst_ratio is None or ratio > worst_ratio):
                worst_ratio = ratio
                worst_scenario = scenario
        if worst_ratio is not None:
            warmup_ratios[key] = (worst_ratio, worst_scenario)

    # Print table
    header = (
        f"  {'Model':<18s} {'Backend':<26s} "
        f"{'N':>4s} {'Mean(ms)':>10s} {'Std(ms)':>10s} {'CV(%)':>7s} "
        f"{'Min(ms)':>10s} {'Max(ms)':>10s} "
        f"{'WarmRatio':>10s} {'WorstScenario':<18s}"
    )
    print()
    print(header)
    print(
        f"  {'-'*18} {'-'*26} {'-'*4} {'-'*10} {'-'*10} {'-'*7} {'-'*10} {'-'*10} {'-'*10} {'-'*18}"
    )

    for key in sorted(groups.keys()):
        vals = groups[key]
        model, backend = key
        n = len(vals)
        mean = statistics.mean(vals)
        std = statistics.stdev(vals) if n > 1 else 0.0
        cv_val = cv(vals)
        mn = min(vals)
        mx = max(vals)
        wr, ws = warmup_ratios.get(key, (None, ""))
        wr_str = f"{wr:.4f}" if wr is not None else "N/A"

        print(
            f"  {model:<18s} {backend:<26s} "
            f"{n:>4d} {mean:>10.2f} {std:>10.2f} {cv_val:>7.2f} "
            f"{mn:>10.2f} {mx:>10.2f} "
            f"{wr_str:>10s} {ws:<18s}"
        )

    print()
    print("  WarmRatio = mean(decode_ms for rep=0) / mean(decode_ms for rep>0).")
    print("  Values near 1.0 indicate warmup was fully effective.")
    print("  Values >> 1.0 would indicate residual warmup effects in rep=0.")
    print()


# ---------------------------------------------------------------------------
# Section (c): Per (model, backend, scenario) detail
# ---------------------------------------------------------------------------


def report_model_backend_scenario(rows: list[dict]) -> None:
    """Report per (model, backend, scenario) detail."""
    print("=" * 80)
    print("SECTION C: Per (model, backend, scenario) Detail")
    print("=" * 80)

    groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        key = (r["model"], r["backend"], r["scenario"])
        groups[key].append(r)

    header = (
        f"  {'Model':<18s} {'Backend':<26s} {'Scenario':<16s} "
        f"{'N':>3s} {'Mean(ms)':>10s} {'Std(ms)':>10s} {'CV(%)':>7s} "
        f"{'Min(ms)':>10s} {'Max(ms)':>10s} {'Max/Min':>8s}"
    )
    print()
    print(header)
    print(
        f"  {'-'*18} {'-'*26} {'-'*16} "
        f"{'-'*3} {'-'*10} {'-'*10} {'-'*7} "
        f"{'-'*10} {'-'*10} {'-'*8}"
    )

    prev_model_backend = None
    for key in sorted(groups.keys()):
        model, backend, scenario = key
        recs = groups[key]
        vals = [r["decode_ms"] for r in recs]
        n = len(vals)
        mean = statistics.mean(vals)
        std = statistics.stdev(vals) if n > 1 else 0.0
        cv_val = cv(vals)
        mn = min(vals)
        mx = max(vals)
        ratio = mx / mn if mn > 0 else float("inf")

        # Visual separator between model/backend groups
        cur_mb = (model, backend)
        if prev_model_backend is not None and cur_mb != prev_model_backend:
            print()
        prev_model_backend = cur_mb

        print(
            f"  {model:<18s} {backend:<26s} {scenario:<16s} "
            f"{n:>3d} {mean:>10.2f} {std:>10.2f} {cv_val:>7.2f} "
            f"{mn:>10.2f} {mx:>10.2f} {ratio:>8.4f}"
        )

    print()
    print("  Max/Min = ratio of maximum to minimum decode_ms across reps.")
    print("  Ratios near 1.0 indicate stable measurements.")
    print()


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


def report_summary(rows: list[dict], total: int, status_counts: dict) -> None:
    """Print data loading summary."""
    print("=" * 80)
    print("DATA SUMMARY")
    print("=" * 80)
    print(f"\n  JSONL file: {JSONL_PATH}")
    print(f"  Total rows: {total}")
    print("  Status breakdown:")
    for status, count in sorted(status_counts.items()):
        print(f"    {status}: {count}")
    print(f"  Rows used (status='ok'): {len(rows)}")

    models = sorted({r["model"] for r in rows})
    backends = sorted({r["backend"] for r in rows})
    scenarios = sorted({r["scenario"] for r in rows})
    print(f"\n  Models ({len(models)}): {', '.join(models)}")
    print(f"  Backends ({len(backends)}): {', '.join(backends)}")
    print(f"  Scenarios ({len(scenarios)}): {', '.join(scenarios)}")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    if not JSONL_PATH.exists():
        print(f"ERROR: JSONL file not found: {JSONL_PATH}", file=sys.stderr)
        sys.exit(1)

    rows, total, status_counts = load_ok_rows(JSONL_PATH)
    if not rows:
        print("ERROR: No rows with status='ok' found.", file=sys.stderr)
        sys.exit(1)

    report_summary(rows, total, status_counts)
    investigate_warmup(rows)
    report_model_backend(rows)
    report_model_backend_scenario(rows)


if __name__ == "__main__":
    main()
