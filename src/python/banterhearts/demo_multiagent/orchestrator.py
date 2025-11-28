"""Aggregation helpers for multi-agent runs."""

from __future__ import annotations

from typing import Any, Dict, List


def build_prompts() -> Dict[str, str]:
    """
    Build prompt templates for multi-agent benchmark scenarios.

    Returns:
        Dict[str, str]: Dictionary mapping agent roles to their prompts:
            - "collector": Prompt for DataCollector-9000 agent (data inventory task)
            - "insight": Prompt for InsightAgent (performance analysis task)
    """
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
    """
    Aggregate metrics across multiple benchmark runs.

    Computes average values for key performance metrics including concurrency
    speedup, efficiency, throughput delta, and TTFT delta.

    Args:
        runs: List of run result dictionaries, each containing metrics from
            a single benchmark execution

    Returns:
        Dict[str, Any]: Aggregated results containing:
            - runs: Original list of run results
            - aggregate: Dictionary with average metrics:
                - average_concurrency_speedup: Average speedup factor
                - average_efficiency: Average efficiency percentage
                - average_throughput_delta: Average throughput difference
                - average_ttft_delta_ms: Average TTFT difference in milliseconds
    """
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
