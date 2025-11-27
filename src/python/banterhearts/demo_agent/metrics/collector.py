"""Simple metrics collector for demo agents."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from statistics import mean
from typing import Any, Dict, List, Optional


@dataclass
class AggregateMetrics:
    request_count: int = 0
    total_tokens_generated: int = 0
    average_tokens_per_second: float = 0.0
    average_ttft_ms: float = 0.0
    total_duration_ms: float = 0.0
    start_time: Optional[str] = None
    end_time: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MetricsCollector:
    def __init__(self, model: str) -> None:
        self.model = model
        self.records: List[Dict[str, Any]] = []
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None

    def start_collection(self) -> None:
        self.start_time = datetime.now()

    def stop_collection(self) -> None:
        self.end_time = datetime.now()

    async def record_request(
        self, prompt: str, response_text: str, result: Dict[str, Any]
    ) -> None:
        """Capture token counts and timings from Ollama result."""
        eval_count = int(result.get("eval_count") or 0)
        eval_duration_ns = int(result.get("eval_duration") or 0)
        prompt_eval_duration_ns = int(result.get("prompt_eval_duration") or 0)
        total_duration_ns = eval_duration_ns + prompt_eval_duration_ns

        throughput = (
            (eval_count / (eval_duration_ns / 1e9))
            if eval_duration_ns and eval_duration_ns > 0
            else 0.0
        )
        ttft_ms = (prompt_eval_duration_ns / 1e6) if prompt_eval_duration_ns else 0.0

        self.records.append(
            {
                "prompt": prompt,
                "response_length": len(response_text or ""),
                "tokens_generated": eval_count,
                "throughput_tok_s": throughput,
                "ttft_ms": ttft_ms,
                "total_duration_ms": total_duration_ns / 1e6 if total_duration_ns else 0,
            }
        )

    def get_aggregate_metrics(self) -> AggregateMetrics:
        if not self.records:
            return AggregateMetrics()

        tokens = [r["tokens_generated"] for r in self.records]
        throughputs = [r["throughput_tok_s"] for r in self.records if r["throughput_tok_s"]]
        ttfts = [r["ttft_ms"] for r in self.records if r["ttft_ms"]]
        durations = [r["total_duration_ms"] for r in self.records]

        agg = AggregateMetrics(
            request_count=len(self.records),
            total_tokens_generated=sum(tokens),
            average_tokens_per_second=mean(throughputs) if throughputs else 0.0,
            average_ttft_ms=mean(ttfts) if ttfts else 0.0,
            total_duration_ms=sum(durations),
            start_time=self.start_time.isoformat() if self.start_time else None,
            end_time=self.end_time.isoformat() if self.end_time else None,
        )
        return agg
