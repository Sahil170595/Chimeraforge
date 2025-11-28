"""Common base classes and data containers for demo agents."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class BenchmarkData:
    """
    Container for benchmark data loaded from files.

    Attributes:
        source_file: Relative path to the source file
        data_type: File type extension (e.g., "csv", "json", "md")
        content: Parsed file content (dict for CSV/JSON, str for markdown)
        metadata: Additional file metadata (size, modification time, etc.)
    """

    source_file: str
    data_type: str
    content: Any
    metadata: Dict[str, Any]


@dataclass
class AnalysisResult:
    """
    Container for structured analysis results from LLM processing.

    Attributes:
        summary: Executive summary of the analysis
        key_findings: List of key findings or insights
        performance_metrics: Dictionary of extracted performance metrics
        recommendations: List of optimization recommendations
    """

    summary: str
    key_findings: List[str]
    performance_metrics: Dict[str, Any]
    recommendations: List[str]


class BaseAgent:
    """
    Lightweight base class that coordinates ingest/analyze/report/metrics workflow.

    Provides a common interface for agent implementations with standardized
    execution flow: ingest benchmarks, analyze data, generate report, collect metrics.

    Subclasses must implement:
        - ingest_benchmarks(): Load benchmark data from filesystem
        - analyze_data(): Process data using LLM
        - generate_report(): Create formatted report
        - get_metrics(): Return performance metrics

    Attributes:
        model: Ollama model name to use
        config: Ollama configuration options dictionary
        ollama_base_url: Base URL for Ollama API
        _run_start: Timestamp when execution started
        _run_end: Timestamp when execution completed
    """

    def __init__(self, model: str, config: Dict[str, Any], *, base_url: str) -> None:
        """
        Initialize the base agent.

        Args:
            model: Ollama model name (e.g., "gemma3:latest")
            config: Dictionary of Ollama configuration options
            base_url: Base URL for Ollama API (e.g., "http://localhost:11434")
        """
        self.model = model
        self.config = config
        self.ollama_base_url = base_url
        self._run_start: Optional[datetime] = None
        self._run_end: Optional[datetime] = None

    async def run_full_analysis(self) -> Dict[str, Any]:
        """
        Execute the complete analysis workflow end-to-end.

        Orchestrates the full pipeline: ingest benchmarks, analyze data,
        generate report, and collect metrics. Used by the demo orchestrator.

        Returns:
            Dict[str, Any]: Complete results dictionary containing:
                - model: Model name used
                - config: Configuration options used
                - analysis: Structured analysis results
                - report: Generated markdown report
                - metrics: Performance metrics
                - execution_summary: Timing information
        """
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
        """
        Load benchmark data from the filesystem.

        Returns:
            List[BenchmarkData]: List of loaded benchmark data objects

        Raises:
            NotImplementedError: Must be implemented by subclasses
        """
        raise NotImplementedError

    async def analyze_data(  # pragma: no cover
        self, benchmark_data: List[BenchmarkData]
    ) -> AnalysisResult:
        """
        Process and analyze benchmark data using LLM.

        Args:
            benchmark_data: List of benchmark data to analyze

        Returns:
            AnalysisResult: Structured analysis results

        Raises:
            NotImplementedError: Must be implemented by subclasses
        """
        raise NotImplementedError

    async def generate_report(self, analysis: AnalysisResult) -> str:  # pragma: no cover
        """
        Generate a formatted markdown report from analysis results.

        Args:
            analysis: Analysis results to format into report

        Returns:
            str: Formatted markdown report

        Raises:
            NotImplementedError: Must be implemented by subclasses
        """
        raise NotImplementedError

    async def get_metrics(self) -> Dict[str, Any]:  # pragma: no cover
        """
        Return performance metrics collected during execution.

        Returns:
            Dict[str, Any]: Dictionary of performance metrics

        Raises:
            NotImplementedError: Must be implemented by subclasses
        """
        raise NotImplementedError

    def get_execution_summary(self) -> Dict[str, Any]:
        """
        Provide a minimal execution summary used in reports.

        Returns:
            Dict[str, Any]: Dictionary containing:
                - start_time: ISO format timestamp of execution start
                - end_time: ISO format timestamp of execution end
                - duration_seconds: Total execution duration
            Returns empty dict if execution hasn't started yet.
        """
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
    """
    Read text file asynchronously using executor.

    Args:
        path: Path object to read from

    Returns:
        str: File contents as UTF-8 string
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, path.read_text, "utf-8")
