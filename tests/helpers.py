"""Shared test helpers for ChimeraForge tests."""

from __future__ import annotations

import json
from pathlib import Path


def make_result(
    model: str = "llama3.2-3b",
    backend: str = "ollama",
    quant: str | None = None,
    throughput_mean: float = 95.0,
    ttft_mean: float = 50.0,
    duration_mean: float = 1000.0,
    runs: int = 5,
    workload: str = "single",
    context_length: int = 2048,
) -> dict:
    """Build a synthetic bench result dict for testing."""
    return {
        "model": model,
        "backend": backend,
        "quant": quant,
        "workload": workload,
        "context_length": context_length,
        "runs": runs,
        "aggregate": {
            "count": runs,
            "throughput_tps": {
                "mean": throughput_mean,
                "p50": throughput_mean,
                "p95": throughput_mean,
                "p99": throughput_mean,
                "min": throughput_mean,
                "max": throughput_mean,
                "stddev": 0.5,
            },
            "ttft_ms": {
                "mean": ttft_mean,
                "p50": ttft_mean,
                "p95": ttft_mean,
                "p99": ttft_mean,
                "min": ttft_mean,
                "max": ttft_mean,
                "stddev": 1.0,
            },
            "total_duration_ms": {
                "mean": duration_mean,
                "p50": duration_mean,
                "p95": duration_mean,
                "p99": duration_mean,
                "min": duration_mean,
                "max": duration_mean,
                "stddev": 10.0,
            },
            "tokens_generated": 640,
        },
        "individual_runs": [],
        "environment": {
            "os": "Windows 11",
            "gpu_name": "RTX 4080",
            "python_version": "3.10.0",
        },
        "timestamp": "2026-01-01T00:00:00+00:00",
        "warnings": [],
    }


def write_bench_json(path: Path, results: list[dict]) -> None:
    """Write a list of bench result dicts to a JSON file."""
    path.write_text(json.dumps(results, indent=2))
