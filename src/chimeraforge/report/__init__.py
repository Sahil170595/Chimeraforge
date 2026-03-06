"""ChimeraForge Report Generation -- Markdown, HTML, and Rich terminal reports.

Public API:
    generate_report     Generate a report from bench result files
    save_report         Write a report to disk
    load_results        Load bench result JSON files
    format_report_rich  Print Rich-formatted summary to console
    Report              Generated report container
    ReportConfig        Report generation configuration
    AnalysisStats       Statistical summary of prediction accuracy
    BenchSummaryRow     One row in a benchmark summary table
    analyze             Compute prediction accuracy statistics
    summarize_bench_results  Extract summary rows from bench results
"""

from chimeraforge.report.analysis import (
    AnalysisStats,
    BenchSummaryRow,
    analyze,
    compute_mae,
    compute_mape,
    compute_r_squared,
    compute_rmse,
    summarize_bench_results,
)
from chimeraforge.report.generator import (
    Report,
    ReportConfig,
    format_report_rich,
    generate_html,
    generate_markdown,
    generate_report,
    load_results,
    save_report,
)

__all__ = [
    "AnalysisStats",
    "BenchSummaryRow",
    "Report",
    "ReportConfig",
    "analyze",
    "compute_mae",
    "compute_mape",
    "compute_r_squared",
    "compute_rmse",
    "format_report_rich",
    "generate_html",
    "generate_markdown",
    "generate_report",
    "load_results",
    "save_report",
    "summarize_bench_results",
]
