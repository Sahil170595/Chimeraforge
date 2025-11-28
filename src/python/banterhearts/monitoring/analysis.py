"""Metric analysis utilities and SLO evaluation helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from statistics import mean
from typing import Dict, Iterable, List, Tuple


@dataclass
class MetricPoint:
    name: str
    value: float
    unit: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class SLO:
    """Simple SLO definition with comparator semantics."""

    name: str
    target: float
    comparator: str = "<="
    window_min_samples: int = 1

    def evaluate(self, stats: Dict[str, float]) -> Tuple[bool, str]:
        sample_count = int(stats.get("count", 0))
        if sample_count < self.window_min_samples:
            return False, f"{self.name}: insufficient samples ({sample_count}/{self.window_min_samples})"

        value = stats.get("p95", stats.get("avg", 0.0))
        if self.comparator == "<=":
            ok = value <= self.target
        elif self.comparator == ">=":
            ok = value >= self.target
        else:
            ok = False
        msg = f"{self.name}: {value:.2f} {stats.get('unit','')} vs target {self.comparator} {self.target}"
        return ok, msg


def _percentile(sorted_values: List[float], pct: float) -> float:
    if not sorted_values:
        return 0.0
    k = (len(sorted_values) - 1) * pct
    f = int(k)
    c = min(f + 1, len(sorted_values) - 1)
    if f == c:
        return sorted_values[int(k)]
    d0 = sorted_values[f] * (c - k)
    d1 = sorted_values[c] * (k - f)
    return d0 + d1


def summarize_metric(points: Iterable[MetricPoint]) -> Dict[str, float]:
    vals = [p.value for p in points]
    if not vals:
        return {"count": 0}
    vals_sorted = sorted(vals)
    return {
        "count": len(vals),
        "avg": mean(vals),
        "p50": _percentile(vals_sorted, 0.5),
        "p90": _percentile(vals_sorted, 0.9),
        "p95": _percentile(vals_sorted, 0.95),
        "p99": _percentile(vals_sorted, 0.99),
        "min": vals_sorted[0],
        "max": vals_sorted[-1],
        "unit": getattr(points[0], "unit", ""),
    }


def analyze_metrics(points: List[MetricPoint], slos: List[SLO] | None = None) -> Dict[str, Dict[str, float]]:
    by_name: Dict[str, List[MetricPoint]] = {}
    for point in points:
        by_name.setdefault(point.name, []).append(point)

    summary = {name: summarize_metric(bucket) for name, bucket in by_name.items()}

    slo_results = []
    if slos:
        for slo in slos:
            stats = summary.get(slo.name, {"count": 0})
            ok, msg = slo.evaluate(stats)
            slo_results.append({"name": slo.name, "ok": ok, "message": msg})

    if slo_results:
        summary["_slos"] = {"results": slo_results}

    return summary
