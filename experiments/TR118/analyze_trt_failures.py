#!/usr/bin/env python3
"""
Classify TensorRT failures (hard vs soft) from TR118 raw JSONL results.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line))
    return rows


def _classify_error(err: str) -> str:
    e = err.lower()
    if "set_input_shape_failed" in e or "profile" in e or "invalid argument" in e:
        return "profile_mismatch"
    if "timeout" in e:
        return "timeout"
    if "no_room_for_generation" in e or "generate_failed" in e:
        return "uncached_generation"
    return "other"


def _is_degraded(row: dict[str, Any]) -> bool:
    if str(row.get("status", "ok")) != "ok":
        return True
    if int(row.get("degraded_count", 0) or 0) > 0:
        return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Classify TRT failures from JSONL")
    parser.add_argument(
        "--roots",
        nargs="*",
        default=[
            "scripts/tr118/results/tr118v2/20251213_135135_deep",
        ],
        help="Root directories to scan for raw JSONL files",
    )
    parser.add_argument(
        "--output",
        default="scripts/tr118/results/tr118v2_audit/trt_failures.json",
        help="Output JSON path",
    )
    args = parser.parse_args()

    summary: dict[str, Any] = {"sources": [], "failures": {}}

    for root_str in args.roots:
        root = Path(root_str)
        if not root.exists():
            continue
        jsonl_files = list(root.rglob("raw/bench_*_*.jsonl"))
        for jsonl_path in jsonl_files:
            rows = _load_jsonl(jsonl_path)
            if not rows:
                continue
            summary["sources"].append(str(jsonl_path))
            for row in rows:
                backend = str(row.get("spec", {}).get("backend", "unknown"))
                if not backend.startswith("tensorrt"):
                    continue
                if not _is_degraded(row):
                    continue
                mode = str(row.get("spec", {}).get("mode", "unknown"))
                err = str(row.get("error") or "")
                failure_type = _classify_error(err)
                key = f"{backend}:{mode}:{failure_type}"
                summary["failures"][key] = summary["failures"].get(key, 0) + 1

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Wrote TRT failure analysis to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
