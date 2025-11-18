"""
Report Quality Analysis Tool

Compares generated agent reports against the actual Technical Report 108
to measure quality improvements from Chimera optimization.
"""

import asyncio
import json
import re
from pathlib import Path
from typing import Dict, List, Any
from dataclasses import dataclass
from datetime import datetime


@dataclass
class QualityMetrics:
    """Metrics for report quality analysis."""

    word_count: int
    section_count: int
    technical_depth_score: float
    citation_count: int
    data_analysis_score: float
    structure_score: float
    overall_quality_score: float


class ReportQualityAnalyzer:
    """Analyzes quality of generated reports vs actual Technical Report 108."""

    def __init__(self, demo_results_dir: str):
        self.demo_results_dir = Path(demo_results_dir)
        # Get repo root: go up from src/python/banterhearts/demo_agent
        repo_root = Path(__file__).parent.parent.parent.parent.parent
        self.actual_report_path = repo_root / "outputs" / "reports" / "Technical_Report_108.md"

    async def analyze_report_quality(self) -> Dict[str, Any]:
        """Analyze quality of both baseline and Chimera reports."""

        # Load actual Technical Report 108 as reference
        actual_report = await self._load_actual_report()

        # Load generated reports
        baseline_report = await self._load_generated_report("baseline")
        chimera_report = await self._load_generated_report("chimera")

        # Analyze quality metrics
        actual_metrics = self._analyze_report_metrics(actual_report)
        baseline_metrics = self._analyze_report_metrics(baseline_report)
        chimera_metrics = self._analyze_report_metrics(chimera_report)

        # Calculate quality improvements
        quality_comparison = self._compare_quality_metrics(actual_metrics, baseline_metrics, chimera_metrics)

        # Generate detailed analysis
        analysis_report = self._generate_quality_analysis_report(
            actual_report,
            baseline_report,
            chimera_report,
            actual_metrics,
            baseline_metrics,
            chimera_metrics,
            quality_comparison,
        )

        return {
            "actual_metrics": actual_metrics,
            "baseline_metrics": baseline_metrics,
            "chimera_metrics": chimera_metrics,
            "quality_comparison": quality_comparison,
            "analysis_report": analysis_report,
        }

    async def _load_actual_report(self) -> str:
        """Load the actual Technical Report 108."""
        try:
            with open(self.actual_report_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            print(f"[WARNING] Technical Report 108 not found at {self.actual_report_path}")
            return ""

    async def _load_generated_report(self, agent_type: str) -> str:
        """Load generated report from demo results."""
        report_path = self.demo_results_dir / "reports" / f"{agent_type}_report_run_1.md"
        try:
            with open(report_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            print(f"[WARNING] {agent_type} report not found at {report_path}")
            return ""

    def _analyze_report_metrics(self, report_content: str) -> QualityMetrics:
        """Analyze quality metrics of a report."""
        if not report_content:
            return QualityMetrics(0, 0, 0.0, 0, 0.0, 0.0, 0.0)

        # Basic metrics
        word_count = len(report_content.split())
        section_count = len(re.findall(r"^#+\s+", report_content, re.MULTILINE))

        # Technical depth analysis
        technical_keywords = [
            "performance",
            "throughput",
            "latency",
            "optimization",
            "benchmark",
            "metrics",
            "analysis",
            "configuration",
            "GPU",
            "memory",
            "utilization",
            "efficiency",
            "scalability",
            "architecture",
            "algorithm",
        ]
        technical_depth_score = self._calculate_technical_depth(report_content, technical_keywords)

        # Citation analysis
        citation_count = len(re.findall(r"\[.*?\]|\(.*?\)|Technical Report|Section \d+", report_content))

        # Data analysis score
        data_analysis_score = self._calculate_data_analysis_score(report_content)

        # Structure score
        structure_score = self._calculate_structure_score(report_content)

        # Overall quality score (weighted average)
        overall_quality_score = (
            technical_depth_score * 0.3 + data_analysis_score * 0.25 + structure_score * 0.25 + min(citation_count / 10, 1.0) * 0.2  # Normalize citations
        )

        return QualityMetrics(
            word_count=word_count,
            section_count=section_count,
            technical_depth_score=technical_depth_score,
            citation_count=citation_count,
            data_analysis_score=data_analysis_score,
            structure_score=structure_score,
            overall_quality_score=overall_quality_score,
        )

    def _calculate_technical_depth(self, content: str, keywords: List[str]) -> float:
        """Calculate technical depth score based on keyword density."""
        content_lower = content.lower()
        keyword_matches = sum(1 for keyword in keywords if keyword in content_lower)
        return min(keyword_matches / len(keywords), 1.0)

    def _calculate_data_analysis_score(self, content: str) -> float:
        """Calculate data analysis quality score."""
        # Look for data analysis indicators
        analysis_indicators = [
            "table",
            "chart",
            "graph",
            "metric",
            "statistic",
            "average",
            "median",
            "percentile",
            "correlation",
            "trend",
            "pattern",
            "insight",
            "finding",
            "comparison",
            "baseline",
            "improvement",
            "delta",
            "variance",
        ]

        content_lower = content.lower()
        matches = sum(1 for indicator in analysis_indicators if indicator in content_lower)
        return min(matches / len(analysis_indicators), 1.0)

    def _calculate_structure_score(self, content: str) -> float:
        """Calculate report structure quality score."""
        # Check for proper report structure
        structure_elements = [
            r"^#\s+.*",  # Main title
            r"^##\s+.*",  # Major sections
            r"^###\s+.*",  # Subsections
            r"^\*\*.*\*\*",  # Bold text
            r"^\|.*\|",  # Tables
            r"^\d+\.\s+",  # Numbered lists
            r"^-\s+",  # Bullet points
        ]

        structure_score = 0
        for pattern in structure_elements:
            if re.search(pattern, content, re.MULTILINE):
                structure_score += 1

        return structure_score / len(structure_elements)

    def _compare_quality_metrics(self, actual: QualityMetrics, baseline: QualityMetrics, chimera: QualityMetrics) -> Dict[str, Any]:
        """Compare quality metrics between reports."""
        return {
            "baseline_vs_actual": {
                "word_count_ratio": baseline.word_count / actual.word_count if actual.word_count > 0 else 0,
                "technical_depth_ratio": baseline.technical_depth_score / actual.technical_depth_score if actual.technical_depth_score > 0 else 0,
                "overall_quality_ratio": baseline.overall_quality_score / actual.overall_quality_score if actual.overall_quality_score > 0 else 0,
            },
            "chimera_vs_actual": {
                "word_count_ratio": chimera.word_count / actual.word_count if actual.word_count > 0 else 0,
                "technical_depth_ratio": chimera.technical_depth_score / actual.technical_depth_score if actual.technical_depth_score > 0 else 0,
                "overall_quality_ratio": chimera.overall_quality_score / actual.overall_quality_score if actual.overall_quality_score > 0 else 0,
            },
            "chimera_vs_baseline": {
                "word_count_improvement": ((chimera.word_count - baseline.word_count) / baseline.word_count * 100) if baseline.word_count > 0 else 0,
                "technical_depth_improvement": (
                    ((chimera.technical_depth_score - baseline.technical_depth_score) / baseline.technical_depth_score * 100)
                    if baseline.technical_depth_score > 0
                    else 0
                ),
                "overall_quality_improvement": (
                    ((chimera.overall_quality_score - baseline.overall_quality_score) / baseline.overall_quality_score * 100)
                    if baseline.overall_quality_score > 0
                    else 0
                ),
            },
        }

    def _generate_quality_analysis_report(
        self,
        actual_report: str,
        baseline_report: str,
        chimera_report: str,
        actual_metrics: QualityMetrics,
        baseline_metrics: QualityMetrics,
        chimera_metrics: QualityMetrics,
        quality_comparison: Dict[str, Any],
    ) -> str:
        """Generate comprehensive quality analysis report."""

        chimera_vs_baseline = quality_comparison["chimera_vs_baseline"]
        baseline_vs_actual = quality_comparison["baseline_vs_actual"]
        chimera_vs_actual = quality_comparison["chimera_vs_actual"]

        table_rows = "\n".join(
            [
                "| Metric | Technical Report 108 | Baseline Agent | Chimera Agent | Chimera Improvement |",
                "|--------|---------------------|----------------|---------------|-------------------|",
                (
                    "| **Word Count** | "
                    f"{actual_metrics.word_count:,} | "
                    f"{baseline_metrics.word_count:,} | "
                    f"{chimera_metrics.word_count:,} | "
                    f"{chimera_vs_baseline['word_count_improvement']:+.1f}% |"
                ),
                (
                    "| **Sections** | "
                    f"{actual_metrics.section_count} | "
                    f"{baseline_metrics.section_count} | "
                    f"{chimera_metrics.section_count} | - |"
                ),
                (
                    "| **Technical Depth** | "
                    f"{actual_metrics.technical_depth_score:.3f} | "
                    f"{baseline_metrics.technical_depth_score:.3f} | "
                    f"{chimera_metrics.technical_depth_score:.3f} | "
                    f"{chimera_vs_baseline['technical_depth_improvement']:+.1f}% |"
                ),
                (
                    "| **Citations** | "
                    f"{actual_metrics.citation_count} | "
                    f"{baseline_metrics.citation_count} | "
                    f"{chimera_metrics.citation_count} | - |"
                ),
                (
                    "| **Data Analysis** | "
                    f"{actual_metrics.data_analysis_score:.3f} | "
                    f"{baseline_metrics.data_analysis_score:.3f} | "
                    f"{chimera_metrics.data_analysis_score:.3f} | - |"
                ),
                (
                    "| **Structure** | "
                    f"{actual_metrics.structure_score:.3f} | "
                    f"{baseline_metrics.structure_score:.3f} | "
                    f"{chimera_metrics.structure_score:.3f} | - |"
                ),
                (
                    "| **Overall Quality** | "
                    f"{actual_metrics.overall_quality_score:.3f} | "
                    f"{baseline_metrics.overall_quality_score:.3f} | "
                    f"{chimera_metrics.overall_quality_score:.3f} | "
                    f"{chimera_vs_baseline['overall_quality_improvement']:+.1f}% |"
                ),
            ]
        )

        baseline_summary = "\n".join(
            [
                (
                    f"- Word Count: {baseline_metrics.word_count:,} words "
                    f"({baseline_vs_actual['word_count_ratio']:.1%} of actual report)"
                ),
                (
                    f"- Technical Depth: {baseline_metrics.technical_depth_score:.3f} "
                    f"({baseline_vs_actual['technical_depth_ratio']:.1%} of actual report)"
                ),
                (
                    f"- Overall Quality: {baseline_metrics.overall_quality_score:.3f} "
                    f"({baseline_vs_actual['overall_quality_ratio']:.1%} of actual report)"
                ),
            ]
        )

        chimera_summary = "\n".join(
            [
                (
                    f"- Word Count: {chimera_metrics.word_count:,} words "
                    f"({chimera_vs_actual['word_count_ratio']:.1%} of actual report)"
                ),
                (
                    f"- Technical Depth: {chimera_metrics.technical_depth_score:.3f} "
                    f"({chimera_vs_actual['technical_depth_ratio']:.1%} of actual report)"
                ),
                (
                    f"- Overall Quality: {chimera_metrics.overall_quality_score:.3f} "
                    f"({chimera_vs_actual['overall_quality_ratio']:.1%} of actual report)"
                ),
            ]
        )

        content_volume_summary = (
            "more" if chimera_metrics.word_count > baseline_metrics.word_count else "fewer"
        )
        technical_depth_summary = (
            "better"
            if chimera_metrics.technical_depth_score > baseline_metrics.technical_depth_score
            else "similar"
        )
        overall_quality_summary = (
            "higher"
            if chimera_metrics.overall_quality_score > baseline_metrics.overall_quality_score
            else "similar"
        )

        quality_recommendation = (
            "Chimera optimization improves report quality"
            if chimera_metrics.overall_quality_score > baseline_metrics.overall_quality_score
            else "Baseline and Chimera show similar quality"
        )
        focus_recommendation = (
            "Focus on Chimera for production use"
            if chimera_metrics.overall_quality_score > baseline_metrics.overall_quality_score
            else "Both configurations are viable"
        )

        quality_impact_description = (
            "demonstrates measurable quality improvements"
            if chimera_metrics.overall_quality_score > baseline_metrics.overall_quality_score
            else "shows similar quality to baseline"
        )
        impact_magnitude = (
            "significant" if abs(chimera_vs_baseline["overall_quality_improvement"]) > 10 else "modest"
        )
        impact_direction = (
            "improvement" if chimera_vs_baseline["overall_quality_improvement"] > 0 else "difference"
        )
        overall_quality_delta = chimera_vs_baseline["overall_quality_improvement"]

        report = f"""# Report Quality Analysis: Chimera vs Baseline vs Technical Report 108

**Analysis Date:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**Reference:** Technical Report 108 (Actual)
**Comparison:** Baseline Agent vs Chimera-Optimized Agent

## Executive Summary

This analysis compares the quality of reports generated by baseline and
Chimera-optimized agents against the actual Technical Report 108 to measure
the impact of Chimera optimization on report quality.

## Quality Metrics Comparison

{table_rows}

## Detailed Analysis

### Content Quality Assessment

**Baseline Agent Report:**
{baseline_summary}

**Chimera-Optimized Agent Report:**
{chimera_summary}

### Key Findings

1. **Content Volume**: Chimera generates {content_volume_summary} content than baseline
2. **Technical Depth**: Chimera shows {technical_depth_summary} technical depth
3. **Overall Quality**: Chimera achieves {overall_quality_summary} overall quality

### Recommendations

Based on this analysis:
- {quality_recommendation}
- {focus_recommendation}
- Consider additional training data to improve technical depth scores

## Conclusion

Chimera optimization {quality_impact_description} in report generation, with {impact_magnitude} overall
quality {impact_direction}.

**Quality Impact:** {overall_quality_delta:+.1f}% overall quality change
"""

        return report


async def main():
    """Main entry point for report quality analysis."""
    analyzer = ReportQualityAnalyzer("demo_agent")

    try:
        results = await analyzer.analyze_report_quality()

        # Save analysis results
        output_path = Path("demo_agent/reports/quality_analysis_report.md")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(results["analysis_report"])

        # Save metrics data
        metrics_path = Path("demo_agent/data/quality_metrics.json")
        with open(metrics_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "actual_metrics": results["actual_metrics"].__dict__,
                    "baseline_metrics": results["baseline_metrics"].__dict__,
                    "chimera_metrics": results["chimera_metrics"].__dict__,
                    "quality_comparison": results["quality_comparison"],
                },
                f,
                indent=2,
            )

        print("Quality analysis completed!")
        print(f"Analysis report saved to: {output_path}")
        print(f"Metrics data saved to: {metrics_path}")

        # Print summary
        comparison = results["quality_comparison"]
        print("\nQuality Summary:")
        print(f"- Chimera vs Baseline Overall Quality: {comparison['chimera_vs_baseline']['overall_quality_improvement']:+.1f}%")
        print(f"- Chimera vs Baseline Technical Depth: {comparison['chimera_vs_baseline']['technical_depth_improvement']:+.1f}%")
        print(f"- Chimera vs Baseline Word Count: {comparison['chimera_vs_baseline']['word_count_improvement']:+.1f}%")

    except Exception as e:
        print(f"Quality analysis failed: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
