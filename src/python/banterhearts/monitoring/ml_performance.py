"""ML performance tracking helpers used by monitoring agents."""

from __future__ import annotations

from typing import Dict, Optional

from .analysis import MetricPoint, SLO
from .agents.aggregator import MetricAggregator


class MLPerformanceTracker:
    def __init__(self, aggregator: Optional[MetricAggregator] = None) -> None:
        self.aggregator = aggregator or MetricAggregator()

    def record_inference(
        self,
        *,
        model: str,
        latency_ms: float,
        tokens_generated: int,
        ttft_ms: Optional[float] = None,
        backend: str = "ollama",
        status: str = "ok",
    ) -> None:
        tags = {"model": model, "backend": backend, "status": status}
        self.aggregator.add_point(MetricPoint("latency_ms", latency_ms, "ms", tags=tags))
        if ttft_ms is not None:
            self.aggregator.add_point(MetricPoint("ttft_ms", ttft_ms, "ms", tags=tags))
        self.aggregator.add_point(MetricPoint("tokens_generated", float(tokens_generated), "tok", tags=tags))
        if latency_ms > 0 and tokens_generated:
            throughput = tokens_generated / (latency_ms / 1000.0)
            self.aggregator.add_point(MetricPoint("throughput_tok_s", throughput, "tok/s", tags=tags))

    def summary(self, slos: Optional[list[SLO]] = None) -> Dict[str, Dict[str, float]]:
        return self.aggregator.summarize(slos=slos)
