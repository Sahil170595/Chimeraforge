"""Helpers for computing benchmark SLIs/SLOs from raw measurements."""

from __future__ import annotations

from typing import Dict, Iterable, List

from .analysis import MetricPoint, summarize_metric


def build_latency_sli(points: Iterable[MetricPoint], threshold_ms: float) -> Dict[str, float]:
    """Return latency stats plus error budget style compliance."""
    stats = summarize_metric(list(points))
    if not stats.get("count"):
        stats["error_budget_burn"] = 1.0
        return stats

    p95 = stats.get("p95", 0.0)
    stats["error_budget_burn"] = max(0.0, p95 - threshold_ms) / max(threshold_ms, 1e-6)
    return stats


def slice_by_tag(points: Iterable[MetricPoint], key: str, value: str) -> List[MetricPoint]:
    return [p for p in points if p.tags.get(key) == value]
