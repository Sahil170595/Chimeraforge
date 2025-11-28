"""Collects metrics and provides rollups."""

from __future__ import annotations

import threading
from typing import Dict, Iterable, List, Optional

from ..analysis import MetricPoint, SLO, analyze_metrics


class MetricAggregator:
    def __init__(self) -> None:
        self.points: List[MetricPoint] = []
        self._lock = threading.Lock()

    def add_point(self, point: MetricPoint) -> None:
        with self._lock:
            self.points.append(point)

    def extend(self, points: Iterable[MetricPoint]) -> None:
        with self._lock:
            self.points.extend(points)

    def filter(self, name: Optional[str] = None, tags: Optional[Dict[str, str]] = None) -> List[MetricPoint]:
        with self._lock:
            source = list(self.points)
        out = source if name is None else [p for p in source if p.name == name]
        if tags:
            out = [p for p in out if all(p.tags.get(k) == v for k, v in tags.items())]
        return out

    def summarize(self, slos: Optional[list[SLO]] = None) -> Dict[str, Dict[str, float]]:
        with self._lock:
            snapshot = list(self.points)
        return analyze_metrics(snapshot, slos=slos)
