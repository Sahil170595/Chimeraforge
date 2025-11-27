"""Aggregation helpers for multi-agent runs."""

from __future__ import annotations

from typing import Any, Dict, List


def build_prompts() -> Dict[str, str]:
    return {
        "collector": (
            "You are DataCollector-9000, a systems analyst tasked with scanning benchmark artifacts.\n"
            "Produce a concise data inventory with bullet points that highlight:\n"
            "1. Directory coverage (reports/, csv_data/, artifacts/).\n"
            "2. File counts per type (md, csv, json) and the latest modified timestamp you observe.\n"
            "3. Any gaps or missing telemetry that could impact model evaluation.\n"
            "Keep the response under 250 words but include concrete metrics so a second agent can reason over them."
        ),
        "insight": (
            "You are InsightAgent, a Chimera-optimised LLM operations specialist.\n"
            "Given the repository context described previously, produce:\n"
            "1. Executive summary of model performance.\n"
            "2. Three optimisation recommendations that balance throughput, TTFT, and quality.\n"
            "3. A risk/mitigation table with at least two rows.\n"
            "Aim for 300-400 words, with numbered sections and bolded metric callouts."
        ),
    }


def aggregate_runs(runs: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not runs:
        return {}

    def avg(key: str) -> float:
        vals = [r.get(key, 0.0) for r in runs if r.get(key) is not None]
        return sum(vals) / len(vals) if vals else 0.0

    return {
        "runs": runs,
        "aggregate": {
            "average_concurrency_speedup": avg("concurrency_speedup"),
            "average_efficiency": avg("efficiency_percent"),
            "average_throughput_delta": avg("throughput_delta"),
            "average_ttft_delta_ms": avg("ttft_delta_ms"),
        },
    }
