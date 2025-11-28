"""
Baseline agent implementation for Chimera demo.

Uses standard Ollama configuration without Chimera optimizations
for performance comparison baseline.
"""

import httpx
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime

try:  # pragma: no cover
    from .base_agent import BaseAgent, BenchmarkData, AnalysisResult
    from ..config.baseline_config import BaselineConfig
    from ..metrics.collector import MetricsCollector
except ImportError:  # pragma: no cover
    from agents.base_agent import BaseAgent, BenchmarkData, AnalysisResult  # type: ignore
    from config.baseline_config import BaselineConfig  # type: ignore
    from metrics.collector import MetricsCollector  # type: ignore


class BaselineAgent(BaseAgent):
    """
    Baseline agent using standard Ollama configuration.

    Implements identical workflow as ChimeraAgent but uses
    default Ollama settings for fair performance comparison.
    """

    def __init__(
        self, model: str = "gemma3:latest", base_url: str = "http://localhost:11434"
    ):
        config = BaselineConfig()
        super().__init__(model, config.to_ollama_options(), base_url=base_url)

        self.baseline_config = config
        self.metrics_collector = MetricsCollector(model)

    async def ingest_benchmarks(self) -> List[BenchmarkData]:
        """Load all benchmark data from outputs/reports/ and data/csv/ directories."""
        benchmark_data = []

        # Get the repository root directory (go up from src/python/banterhearts)
        repo_root = Path(__file__).parent.parent.parent.parent.parent

        # Scan outputs/reports/ directory
        reports_dir = repo_root / "outputs" / "reports"
        if reports_dir.exists():
            for file_path in reports_dir.rglob("*"):
                if file_path.is_file() and file_path.suffix.lower() in [
                    ".csv",
                    ".json",
                    ".md",
                ]:
                    try:
                        content = await self._load_file_content(file_path)
                        if content:
                            benchmark_data.append(
                                BenchmarkData(
                                    source_file=str(
                                        file_path.relative_to(repo_root)
                                    ),
                                    data_type=file_path.suffix.lower()[1:],
                                    content=content,
                                    metadata={
                                        "file_size": file_path.stat().st_size,
                                        "modified_time": file_path.stat().st_mtime,
                                    },
                                )
                            )
                    except Exception as e:
                        print(f"Warning: Could not load {file_path}: {e}")

        # Scan data/csv/ directory
        csv_data_dir = repo_root / "data" / "csv"
        if csv_data_dir.exists():
            for file_path in csv_data_dir.rglob("*"):
                if file_path.is_file() and file_path.suffix.lower() in [
                    ".csv",
                    ".json",
                ]:
                    try:
                        content = await self._load_file_content(file_path)
                        if content:
                            benchmark_data.append(
                                BenchmarkData(
                                    source_file=str(
                                        file_path.relative_to(repo_root)
                                    ),
                                    data_type=file_path.suffix.lower()[1:],
                                    content=content,
                                    metadata={
                                        "file_size": file_path.stat().st_size,
                                        "modified_time": file_path.stat().st_mtime,
                                    },
                                )
                            )
                    except Exception as e:
                        print(f"Warning: Could not load {file_path}: {e}")

        return benchmark_data

    async def _load_file_content(self, file_path: Path) -> Optional[Any]:
        """
        Load content from a file based on its type.

        Supports CSV (loaded as pandas DataFrame converted to dict), JSON, and
        Markdown files. Returns None on error.

        Args:
            file_path: Path to the file to load

        Returns:
            Optional[Any]: File content as:
                - List[Dict] for CSV files
                - Dict or List for JSON files
                - str for Markdown files
                - None if loading fails
        """
        try:
            if file_path.suffix.lower() == ".csv":
                import pandas as pd

                return pd.read_csv(file_path).to_dict("records")
            elif file_path.suffix.lower() == ".json":
                with open(file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            elif file_path.suffix.lower() == ".md":
                with open(file_path, "r", encoding="utf-8") as f:
                    return f.read()
        except Exception as e:
            print(f"Error loading {file_path}: {e}")
            return None

    async def analyze_data(self, benchmark_data: List[BenchmarkData]) -> AnalysisResult:
        """Process and analyze benchmark data using LLM."""
        self.metrics_collector.start_collection()

        # Create analysis prompt
        data_summary = self._create_data_summary(benchmark_data)

        analysis_prompt = f"""
You are a performance analysis expert. Analyze the following benchmark data and provide insights.

Benchmark Data Summary:
{data_summary}

Please provide:
1. Executive summary of the data
2. Key performance findings
3. Performance metrics analysis
4. Recommendations for optimization

Format your response as structured analysis with clear sections.
"""

        # Get LLM analysis
        analysis_response = await self._call_llm(analysis_prompt)

        # Parse the response into structured result
        return AnalysisResult(
            summary=self._extract_summary(analysis_response),
            key_findings=self._extract_findings(analysis_response),
            performance_metrics=self._extract_metrics(benchmark_data),
            recommendations=self._extract_recommendations(analysis_response),
        )

    def _create_data_summary(self, benchmark_data: List[BenchmarkData]) -> str:
        """
        Create a formatted summary of benchmark data for LLM analysis.

        Groups files by type and lists up to 5 files per type with their paths.

        Args:
            benchmark_data: List of BenchmarkData objects to summarize

        Returns:
            str: Formatted summary string with file counts and paths
        """
        summary = f"Total files analyzed: {len(benchmark_data)}\n\n"

        # Group by data type
        by_type = {}
        for data in benchmark_data:
            data_type = data.data_type
            if data_type not in by_type:
                by_type[data_type] = []
            by_type[data_type].append(data)

        for data_type, files in by_type.items():
            summary += f"{data_type.upper()} Files ({len(files)}):\n"
            for file_data in files[:5]:  # Show first 5 files
                summary += f"  - {file_data.source_file}\n"
            if len(files) > 5:
                summary += f"  ... and {len(files) - 5} more\n"
            summary += "\n"

        return summary

    async def _call_llm(self, prompt: str) -> str:
        """
        Make an LLM call with metrics collection.

        Sends a prompt to the Ollama API using the agent's baseline configuration
        and records performance metrics for analysis.

        Args:
            prompt: Text prompt to send to the LLM

        Returns:
            str: Generated text response from the LLM

        Raises:
            RuntimeError: If the Ollama API returns a non-200 status code
        """
        timeout = httpx.Timeout(120.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": self.config,
            }

            response = await client.post(
                f"{self.ollama_base_url}/api/generate", json=payload
            )

            if response.status_code != 200:
                raise RuntimeError(f"Ollama API error: {response.status_code}")

            result = response.json()

            # Record metrics
            await self.metrics_collector.record_request(
                prompt, result.get("response", ""), result
            )

            return result.get("response", "")

    def _extract_summary(self, response: str) -> str:
        """
        Extract executive summary section from LLM response.

        Searches for summary sections by looking for keywords and section headers.
        Falls back to first 500 characters if no summary section is found.

        Args:
            response: Full LLM response text

        Returns:
            str: Extracted summary text or truncated response
        """
        lines = response.split("\n")
        summary_lines = []
        in_summary = False

        for line in lines:
            if "executive summary" in line.lower() or "summary" in line.lower():
                in_summary = True
                continue
            elif in_summary and (
                line.strip().startswith("#") or line.strip().startswith("##")
            ):
                break
            elif in_summary and line.strip():
                summary_lines.append(line.strip())

        return "\n".join(summary_lines) if summary_lines else response[:500] + "..."

    def _extract_findings(self, response: str) -> List[str]:
        """
        Extract key findings from LLM response.

        Searches for lines containing keywords like "finding", "insight", "discovery",
        or "key" and returns up to 10 findings.

        Args:
            response: Full LLM response text

        Returns:
            List[str]: List of extracted finding strings (max 10)
        """
        findings = []
        lines = response.split("\n")

        for line in lines:
            if any(
                keyword in line.lower()
                for keyword in ["finding", "insight", "discovery", "key"]
            ):
                if line.strip() and not line.strip().startswith("#"):
                    findings.append(line.strip())

        return findings[:10]  # Limit to top 10 findings

    def _extract_metrics(self, benchmark_data: List[BenchmarkData]) -> Dict[str, Any]:
        """
        Extract performance metrics from benchmark data.

        Aggregates file counts, types, sizes, and attempts to extract numerical
        performance metrics from CSV data.

        Args:
            benchmark_data: List of BenchmarkData objects to analyze

        Returns:
            Dict[str, Any]: Dictionary containing:
                - total_files_analyzed: Count of files processed
                - data_types: List of unique file types found
                - total_file_size_bytes: Sum of all file sizes
                - csv_*: Any performance metrics found in CSV files
        """
        metrics = {
            "total_files_analyzed": len(benchmark_data),
            "data_types": list(set(data.data_type for data in benchmark_data)),
            "total_file_size_bytes": sum(
                data.metadata.get("file_size", 0) for data in benchmark_data
            ),
        }

        # Try to extract numerical metrics from CSV/JSON data
        for data in benchmark_data:
            if data.data_type == "csv" and isinstance(data.content, list):
                # Look for performance metrics in CSV data
                for row in data.content[:10]:  # Sample first 10 rows
                    if isinstance(row, dict):
                        for key, value in row.items():
                            if "tok" in key.lower() or "throughput" in key.lower():
                                try:
                                    metrics[f"csv_{key}"] = float(value)
                                except (ValueError, TypeError):
                                    pass

        return metrics

    def _extract_recommendations(self, response: str) -> List[str]:
        """
        Extract recommendations from LLM response.

        Searches for lines containing recommendation keywords like "recommend",
        "suggest", "should", or "consider" and returns up to 10.

        Args:
            response: Full LLM response text

        Returns:
            List[str]: List of extracted recommendation strings (max 10)
        """
        recommendations = []
        lines = response.split("\n")

        for line in lines:
            if any(
                keyword in line.lower()
                for keyword in ["recommend", "suggest", "should", "consider"]
            ):
                if line.strip() and not line.strip().startswith("#"):
                    recommendations.append(line.strip())

        return recommendations[:10]  # Limit to top 10 recommendations

    async def generate_report(self, analysis: AnalysisResult) -> str:
        """Generate Technical Report 108-style markdown report."""
        report_prompt = f"""
Generate a comprehensive technical report in the style of Technical Report 108.

Analysis Results:
- Summary: {analysis.summary}
- Key Findings: {analysis.key_findings}
- Performance Metrics: {analysis.performance_metrics}
- Recommendations: {analysis.recommendations}

Create a professional technical report with the following structure:
1. Executive Summary
2. Data Ingestion Summary
3. Performance Analysis
4. Key Findings
5. Recommendations
6. Appendix

Use markdown formatting and include specific metrics and data points.
"""

        report_content = await self._call_llm(report_prompt)

        # Add header information
        header = f"""# Technical Report: Baseline Agent Analysis

**Date:** {datetime.now().strftime("%Y-%m-%d")}
**Agent Type:** Baseline (Standard Ollama Configuration)
**Model:** {self.model}
**Configuration:** {self.baseline_config.get_description()}

---

"""

        return header + report_content

    async def get_metrics(self) -> Dict[str, Any]:
        """Return performance metrics collected during execution."""
        self.metrics_collector.stop_collection()
        aggregate_metrics = self.metrics_collector.get_aggregate_metrics()

        return {
            "agent_type": "baseline",
            "model": self.model,
            "configuration": self.config,
            "aggregate_metrics": aggregate_metrics.__dict__,
            "execution_summary": self.get_execution_summary(),
        }
