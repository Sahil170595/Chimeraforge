"""Enforce separate line/branch floors on coverage.py's JSON evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

# Floors are ratchets; measured baselines and scope are recorded in docs/ci.md.
GLOBAL_FLOORS = (89.0, 82.0)
CRITICAL_FLOORS = {
    "src/chimeraforge/bench/metrics.py": (94.0, 90.0),
    "src/chimeraforge/planner/constants.py": (95.0, 90.0),
}


def rates(summary: dict) -> tuple[float, float]:
    """Reject invalid counters instead of treating absent evidence as 100%."""
    result = []
    for numerator, denominator in (
        ("covered_lines", "num_statements"),
        ("covered_branches", "num_branches"),
    ):
        covered, total = summary[numerator], summary[denominator]
        if type(total) is not int or type(covered) is not int or not 0 <= covered <= total:
            raise ValueError(f"invalid coverage counters: {numerator}/{denominator}")
        if total == 0:
            raise ValueError(f"no evidence for {denominator}")
        result.append(100.0 * covered / total)
    return result[0], result[1]


def check(data: dict) -> tuple[list[str], list[str]]:
    """Return human-readable measurements and failures."""
    rows, failures = [], []
    checks = [("whole package", data["totals"], GLOBAL_FLOORS)]
    files = {name.replace("\\", "/"): value for name, value in data["files"].items()}
    for filename, floor in CRITICAL_FLOORS.items():
        matches = [value for name, value in files.items() if name.endswith(filename)]
        if len(matches) != 1:
            failures.append(f"missing or ambiguous critical module: {filename}")
            continue
        checks.append((filename, matches[0]["summary"], floor))
    for name, summary, floors in checks:
        measured = rates(summary)
        rows.append(f"{name}: line {measured[0]:.2f}%, branch {measured[1]:.2f}%")
        for label, actual, floor in zip(("line", "branch"), measured, floors):
            if actual < floor:
                failures.append(f"{name}: {label} {actual:.2f}% is below {floor:.2f}%")
    return rows, failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--summary", type=Path)
    args = parser.parse_args()
    try:
        rows, failures = check(json.loads(args.report.read_text(encoding="utf-8")))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"::error::coverage evidence could not be validated: {exc}")
        return 1
    for row in rows:
        print(row)
    for failure in failures:
        print(f"::error::{failure}")
    if args.summary:
        with args.summary.open("a", encoding="utf-8") as stream:
            stream.write("## Coverage\n\n" + "\n\n".join(rows + failures) + "\n")
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
