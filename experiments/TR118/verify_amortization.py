#!/usr/bin/env python3
"""
Verify TRT amortization math for the GPT-2 example.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd


def _load_throughput_mean(path: Path, backend: str) -> float | None:
    df = pd.read_csv(path)
    if "degraded_rate" in df.columns:
        df = df[df["degraded_rate"] < 1.0]
    agg = df.groupby("backend")["throughput_mean_tok_s"].mean()
    if backend not in agg:
        return None
    return float(agg[backend])


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify TRT amortization math")
    parser.add_argument(
        "--latency-summary",
        default="scripts/tr118/results/tr118v2/20251213_135135_deep/gpt2/processed/latency_summary_prefill.csv",
        help="Latency summary CSV (prefill)",
    )
    parser.add_argument(
        "--baseline-backend",
        default="transformers-gpu-compile",
        help="Baseline backend",
    )
    parser.add_argument(
        "--target-backend",
        default="tensorrt-int8",
        help="Target backend",
    )
    parser.add_argument(
        "--build-time-s",
        type=float,
        default=240.0,
        help="Build time in seconds",
    )
    parser.add_argument(
        "--output",
        default="scripts/tr118/results/tr118v2_audit/amortization_check.json",
        help="Output JSON path",
    )
    args = parser.parse_args()

    latency_path = Path(args.latency_summary)
    baseline = _load_throughput_mean(latency_path, args.baseline_backend)
    target = _load_throughput_mean(latency_path, args.target_backend)
    if baseline is None or target is None:
        raise SystemExit("Missing throughput data for baseline/target backends")

    delta = target - baseline
    if delta <= 0:
        raise SystemExit("Target backend is not faster than baseline")

    build_time = float(args.build_time_s)
    time_to_recover_s = build_time * baseline / delta
    tokens_to_recover = time_to_recover_s * baseline
    total_time_s = build_time + time_to_recover_s
    total_tokens = total_time_s * baseline
    exact_tokens = build_time * baseline * target / delta

    report: dict[str, Any] = {
        "baseline_backend": args.baseline_backend,
        "target_backend": args.target_backend,
        "baseline_throughput": baseline,
        "target_throughput": target,
        "throughput_delta": delta,
        "build_time_s": build_time,
        "time_to_recover_s": time_to_recover_s,
        "tokens_to_recover_baseline": tokens_to_recover,
        "total_time_s": total_time_s,
        "total_tokens_baseline": total_tokens,
        "exact_tokens_needed": exact_tokens,
        "speedup_ratio": target / baseline,
    }

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote amortization check to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
