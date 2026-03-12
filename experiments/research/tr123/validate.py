#!/usr/bin/env python3
"""
TR123: Data Quality Validation.

Checks raw measurements for completeness, consistency, and sanity
before running the analysis pipeline.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
import logging
from pathlib import Path
import sys
from typing import Any

import yaml

logger = logging.getLogger(__name__)

try:
    from research.shared.statistical_analysis import detect_outliers
except ImportError:

    def detect_outliers(values, method="iqr", threshold=1.5):
        if len(values) < 4:
            return []
        sorted_v = sorted(values)
        q1 = sorted_v[len(sorted_v) // 4]
        q3 = sorted_v[3 * len(sorted_v) // 4]
        iqr = q3 - q1
        lower = q1 - threshold * iqr
        upper = q3 + threshold * iqr
        return [i for i, v in enumerate(values) if v < lower or v > upper]


def load_all_rows(jsonl_path: Path) -> list[dict[str, Any]]:
    rows = []
    with open(jsonl_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def check_completeness(
    rows: list[dict[str, Any]],
    cfg: dict[str, Any],
) -> list[str]:
    """Check if all expected cells are present."""
    issues = []
    backend_skip = cfg.get("backend_skip", {})

    expected_cells = set()
    for m in cfg["models"]:
        model_skips = backend_skip.get(m["name"], [])
        for b in cfg["backends"]:
            if b in model_skips:
                continue
            for s in cfg["scenarios"]:
                for rep in range(cfg.get("repetitions", 7)):
                    expected_cells.add((m["name"], b, s["name"], rep))

    actual_cells = set()
    for row in rows:
        actual_cells.add(
            (
                row.get("model", ""),
                row.get("backend", ""),
                row.get("scenario", ""),
                row.get("rep", 0),
            )
        )

    missing = expected_cells - actual_cells
    if missing:
        issues.append(f"Missing {len(missing)}/{len(expected_cells)} expected cells")
        for cell in sorted(missing)[:5]:
            issues.append(f"  Missing: {cell}")
        if len(missing) > 5:
            issues.append(f"  ... and {len(missing) - 5} more")

    return issues


def check_error_rate(rows: list[dict[str, Any]]) -> list[str]:
    """Check error rate per group (excluding skipped measurements)."""
    issues = []
    groups: dict[tuple, list] = defaultdict(list)

    for row in rows:
        # Skip intentionally skipped measurements (backend_skip entries)
        if row.get("status") == "skipped":
            continue
        key = (row.get("model", ""), row.get("backend", ""))
        groups[key].append(row.get("status", "unknown"))

    for key, statuses in groups.items():
        errors = sum(1 for s in statuses if s != "ok")
        total = len(statuses)
        error_rate = errors / total if total > 0 else 0
        if error_rate > 0.2:
            issues.append(
                f"High error rate for {key[0]}/{key[1]}: "
                f"{errors}/{total} ({error_rate:.0%})"
            )

    return issues


def check_timing_sanity(rows: list[dict[str, Any]]) -> list[str]:
    """Check that prefill_ms + decode_ms ≈ total_ms."""
    issues = []
    bad_count = 0

    ok_rows = [r for r in rows if r.get("status") == "ok"]
    for row in ok_rows:
        prefill = row.get("prefill_ms")
        decode = row.get("decode_ms")
        total = row.get("total_ms")

        if prefill is None or decode is None or total is None:
            continue

        expected = prefill + decode
        if total > 0:
            diff_pct = abs(expected - total) / total
            if diff_pct > 0.05:
                bad_count += 1

    if bad_count > 0:
        issues.append(
            f"Timing mismatch (prefill+decode != total within 5%): "
            f"{bad_count}/{len(ok_rows)} rows"
        )

    return issues


def check_monotonicity(rows: list[dict[str, Any]]) -> list[str]:
    """Check that longer prompts → longer prefill within each backend."""
    issues = []
    ok_rows = [r for r in rows if r.get("status") == "ok"]

    # Group by (model, backend) and sort by prompt_tokens
    groups: dict[tuple, list] = defaultdict(list)
    for row in ok_rows:
        key = (row.get("model", ""), row.get("backend", ""))
        groups[key].append(row)

    for key, group_rows in groups.items():
        # Average prefill_ms per scenario
        scenario_avg: dict[int, list[float]] = defaultdict(list)
        for row in group_rows:
            pt = row.get("prompt_tokens", 0)
            pms = row.get("prefill_ms")
            if pt and pms:
                scenario_avg[pt].append(pms)

        pts = sorted(scenario_avg.keys())
        if len(pts) < 2:
            continue

        avgs = [(pt, sum(vs) / len(vs)) for pt, vs in sorted(scenario_avg.items())]
        for i in range(1, len(avgs)):
            if avgs[i][1] < avgs[i - 1][1] * 0.5:  # Allow some variance
                issues.append(
                    f"Non-monotonic prefill for {key[0]}/{key[1]}: "
                    f"{avgs[i-1][0]}tok={avgs[i-1][1]:.1f}ms > "
                    f"{avgs[i][0]}tok={avgs[i][1]:.1f}ms"
                )

    return issues


def check_thermal_throttling(rows: list[dict[str, Any]]) -> list[str]:
    """Flag measurements that occurred during thermal throttling."""
    issues = []
    ok_rows = [r for r in rows if r.get("status") == "ok"]

    throttled_count = 0
    for row in ok_rows:
        warnings = row.get("warnings", [])
        if any("thermal_throttle" in w for w in warnings):
            throttled_count += 1
        # Also check raw temperature
        temp = row.get("gpu_temp_c")
        if temp is not None and float(temp) >= 80:
            throttled_count += 1

    if throttled_count > 0:
        pct = throttled_count / len(ok_rows) * 100 if ok_rows else 0
        issues.append(
            f"Thermal throttling detected in {throttled_count}/{len(ok_rows)} "
            f"measurements ({pct:.0f}%). Latency/power data may be unreliable."
        )

    return issues


def check_outliers(rows: list[dict[str, Any]]) -> list[str]:
    """Flag statistical outliers in timing measurements."""
    issues = []
    ok_rows = [r for r in rows if r.get("status") == "ok"]

    groups: dict[tuple, list[float]] = defaultdict(list)
    for row in ok_rows:
        key = (row.get("model"), row.get("backend"), row.get("scenario"))
        total = row.get("total_ms")
        if total is not None:
            groups[key].append(float(total))

    for key, values in groups.items():
        if len(values) < 4:
            continue
        outlier_indices = detect_outliers(values)
        if outlier_indices:
            issues.append(
                f"Outliers in {key[0]}/{key[1]}/{key[2]}: "
                f"{len(outlier_indices)}/{len(values)} measurements"
            )

    return issues


def validate(
    jsonl_path: str | Path,
    config_path: str | Path | None = None,
) -> tuple[bool, list[str]]:
    """Run all validation checks. Returns (all_pass, issues)."""
    jsonl_path = Path(jsonl_path)
    rows = load_all_rows(jsonl_path)

    if not rows:
        return False, ["No rows found in JSONL"]

    all_issues: list[str] = []

    # Completeness check (requires config)
    if config_path:
        with open(config_path) as f:
            cfg = yaml.safe_load(f)
        all_issues.extend(check_completeness(rows, cfg))

    all_issues.extend(check_error_rate(rows))
    all_issues.extend(check_timing_sanity(rows))
    all_issues.extend(check_monotonicity(rows))
    all_issues.extend(check_outliers(rows))
    all_issues.extend(check_thermal_throttling(rows))

    ok_count = sum(1 for r in rows if r.get("status") == "ok")
    err_count = sum(1 for r in rows if r.get("status") == "error")
    skip_count = sum(1 for r in rows if r.get("status") == "skipped")

    logger.info(
        f"Validation summary: {ok_count} ok, {err_count} error, {skip_count} skipped"
    )
    for issue in all_issues:
        logger.warning(f"  ISSUE: {issue}")

    all_pass = len(all_issues) == 0
    return all_pass, all_issues


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TR123: Data Validation")
    parser.add_argument("jsonl", help="Path to raw_measurements.jsonl")
    parser.add_argument("--config", default=None, help="Path to matrix.yaml")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    all_pass, issues = validate(args.jsonl, args.config)
    if all_pass:
        print("\nAll validation checks passed.")
    else:
        print(f"\n{len(issues)} validation issue(s) found.")
    sys.exit(0 if all_pass else 1)
