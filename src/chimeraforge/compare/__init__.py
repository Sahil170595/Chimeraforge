"""Compare — diff benchmark result files side by side."""

from chimeraforge.compare.comparator import (
    ComparisonRow,
    compare_results,
    format_comparison_json,
    format_comparison_summary,
    format_comparison_table,
    group_by_key,
    load_results,
    make_key,
)

__all__ = [
    "ComparisonRow",
    "compare_results",
    "format_comparison_json",
    "format_comparison_summary",
    "format_comparison_table",
    "group_by_key",
    "load_results",
    "make_key",
]
