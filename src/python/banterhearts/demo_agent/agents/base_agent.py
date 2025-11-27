"""Common base classes and data containers for demo agents."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class BenchmarkData:
    source_file: str
    data_type: str
    content: Any
    metadata: Dict[str, Any]


@dataclass
class AnalysisResult:
    summary: str
    key_findings: List[str]
    performance_metrics: Dict[str, Any]
    recommendations: List[str]


class BaseAgent:
    """Lightweight base class that coordinates ingest/analyze/report/metrics."""

    def __init__(self, model: str, config: Dict[str, Any], *, base_url: str) -> None:
        self.model = model
        self.config = config
        self.ollama_base_url = base_url
        self._run_start: Optional[datetime] = None
        self._run_end: Optional[datetime] = None

    async def run_full_analysis(self) -> Dict[str, Any]:
        """End-to-end driver used by the orchestrator."""
        self._run_start = datetime.now()

        benchmark_data = await self.ingest_benchmarks()
        analysis = await self.analyze_data(benchmark_data)
        report = await self.generate_report(analysis)
        metrics = await self.get_metrics()

        self._run_end = datetime.now()

        return {
            "model": self.model,
            "config": self.config,
            "analysis": {
                "summary": analysis.summary,
                "key_findings": analysis.key_findings,
                "performance_metrics": analysis.performance_metrics,
                "recommendations": analysis.recommendations,
            },
            "report": report,
            "metrics": metrics,
            "execution_summary": self.get_execution_summary(),
        }

    # Subclasses must implement these
    async def ingest_benchmarks(self) -> List[BenchmarkData]:  # pragma: no cover
        raise NotImplementedError

    async def analyze_data(  # pragma: no cover
        self, benchmark_data: List[BenchmarkData]
    ) -> AnalysisResult:
        raise NotImplementedError

    async def generate_report(self, analysis: AnalysisResult) -> str:  # pragma: no cover
        raise NotImplementedError

    async def get_metrics(self) -> Dict[str, Any]:  # pragma: no cover
        raise NotImplementedError

    def get_execution_summary(self) -> Dict[str, Any]:
        """Provide a minimal execution summary used in reports."""
        if not self._run_start:
            return {}
        end_time = self._run_end or datetime.now()
        return {
            "start_time": self._run_start.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": (end_time - self._run_start).total_seconds(),
        }


# Convenience helper for async file reads (used in subclasses)
async def read_text_async(path) -> str:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, path.read_text, "utf-8")
