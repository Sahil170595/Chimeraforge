#!/usr/bin/env python3
"""
Verify TR118 run counts and degradation rates from raw JSONL files.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml


def _latest(glob: list[Path]) -> Path | None:
    files = [p for p in glob if p.exists()]
    if not files:
        return None
    return sorted(files, key=lambda p: p.stat().st_mtime)[-1]


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line))
    return rows


def _load_config(processed_dir: Path) -> dict[str, Any]:
    cfg_path = _latest(list(processed_dir.glob("config_used_*.yaml")))
    if cfg_path is None:
        return {}
    return yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}


def _count_degraded(rows: list[dict[str, Any]]) -> int:
    count = 0
    for row in rows:
        if str(row.get("status", "ok")) != "ok":
            count += 1
            continue
        if int(row.get("degraded_count", 0) or 0) > 0:
            count += 1
    return count


def _expected_runs(cfg: dict[str, Any], mode: str) -> int | None:
    bench = cfg.get("benchmark", {}) or {}
    backends = bench.get("backends") or []
    scenarios = bench.get("scenarios") or []
    repetitions = int(bench.get("repetitions", 1) or 1)
    modes = bench.get("modes") or [bench.get("mode", "prefill")]
    if mode not in [str(m) for m in modes]:
        return None
    return int(len(backends) * len(scenarios) * repetitions)


def _summarize(raw_path: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    rows = _load_jsonl(raw_path)
    backends = [r.get("spec", {}).get("backend") for r in rows]
    scenarios = [r.get("spec", {}).get("scenario") for r in rows]
    mode = rows[0].get("spec", {}).get("mode") if rows else "unknown"
    expected = _expected_runs(cfg, str(mode))
    degraded = _count_degraded(rows)
    return {
        "raw_path": str(raw_path),
        "mode": mode,
        "total_runs": len(rows),
        "expected_runs": expected,
        "degraded_runs": degraded,
        "degraded_rate": degraded / len(rows) if rows else 0.0,
        "unique_backends": sorted({b for b in backends if b}),
        "unique_scenarios": sorted({s for s in scenarios if s}),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify TR118 run counts from JSONL data")
    parser.add_argument(
        "--root",
        default="scripts/tr118/results/tr118v2/20251213_135135_deep",
        help="Root directory containing model subfolders (tiny-gpt2, gpt2, etc.)",
    )
    parser.add_argument(
        "--models",
        nargs="*",
        default=["tiny-gpt2", "gpt2"],
        help="Model subfolders to verify",
    )
    parser.add_argument(
        "--output",
        default="scripts/tr118/results/tr118v2_audit/run_counts.json",
        help="Output JSON path",
    )
    args = parser.parse_args()

    root = Path(args.root)
    summary: dict[str, Any] = {"root": str(root), "models": {}}

    for model in args.models:
        model_dir = root / model
        processed_dir = model_dir / "processed"
        raw_dir = model_dir / "raw"
        cfg = _load_config(processed_dir)
        summaries: list[dict[str, Any]] = []
        for mode in ["prefill", "generate"]:
            raw_path = _latest(list(raw_dir.glob(f"bench_{mode}_*.jsonl")))
            if raw_path is None:
                continue
            summaries.append(_summarize(raw_path, cfg))
        summary["models"][model] = {
            "processed_dir": str(processed_dir),
            "raw_dir": str(raw_dir),
            "summaries": summaries,
        }

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Wrote run count audit to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
