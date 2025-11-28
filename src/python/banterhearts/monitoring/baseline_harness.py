"""Baseline validation harness for monitoring outputs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from .analysis import SLO


@dataclass
class HarnessResult:
    passed: bool
    failures: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


class BaselineHarness:
    """Evaluate metric summaries against baselines and SLOs."""

    def __init__(self, slos: List[SLO], baselines: Dict[str, float] | None = None) -> None:
        self.slos = slos
        self.baselines = baselines or {}

    def evaluate(self, summary: Dict[str, Dict[str, float]]) -> HarnessResult:
        failures: List[str] = []
        notes: List[str] = []

        for slo in self.slos:
            stats = summary.get(slo.name, {"count": 0})
            ok, message = slo.evaluate(stats)
            if not ok:
                failures.append(message)
            else:
                notes.append(message)

        for metric_name, expected in self.baselines.items():
            if metric_name not in summary:
                failures.append(f"{metric_name}: missing from summary")
                continue
            actual = summary[metric_name].get("avg", 0.0)
            if actual > expected * 1.2:
                failures.append(f"{metric_name}: {actual:.2f} regressed vs baseline {expected:.2f}")
            else:
                notes.append(f"{metric_name}: {actual:.2f} within baseline {expected:.2f}")

        return HarnessResult(passed=not failures, failures=failures, notes=notes)
