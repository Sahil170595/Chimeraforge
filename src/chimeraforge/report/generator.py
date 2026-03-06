"""Report generation in Markdown, HTML, and Rich terminal formats.

Generates self-contained benchmark reports from bench result JSON files.
Markdown output is GitHub-compatible. HTML output is a single file with
inline CSS (no external dependencies or template engines).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rich.console import Console

from chimeraforge.report.analysis import BenchSummaryRow, summarize_bench_results


@dataclass
class ReportConfig:
    """Configuration for report generation.

    Attributes:
        title: Report title.
        format: Output format -- ``"markdown"`` or ``"html"``.
        include_environment: Whether to include environment info section.
        include_warnings: Whether to include warnings section.
    """

    title: str = "ChimeraForge Benchmark Report"
    format: str = "markdown"
    include_environment: bool = True
    include_warnings: bool = True


@dataclass
class Report:
    """Generated report content.

    Attributes:
        title: Report title.
        format: Output format used.
        content: The rendered report body (Markdown or HTML string).
        timestamp: ISO 8601 UTC timestamp of generation.
        n_results: Number of bench results included.
    """

    title: str
    format: str
    content: str
    timestamp: str
    n_results: int


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def load_results(paths: list[Path]) -> list[dict]:
    """Load bench result JSON files.

    Each file may contain a single result dict or a list of result dicts
    (the format produced by ``chimeraforge.bench.runner.save_results``).

    Args:
        paths: Paths to JSON files.

    Returns:
        Flat list of result dicts.

    Raises:
        FileNotFoundError: If a path does not exist.
        json.JSONDecodeError: If a file is not valid JSON.
    """
    results: list[dict] = []
    for p in paths:
        data = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(data, list):
            results.extend(data)
        elif isinstance(data, dict):
            results.append(data)
    return results


# ---------------------------------------------------------------------------
# Markdown generation
# ---------------------------------------------------------------------------


def _md_environment_section(env: dict) -> str:
    """Render the environment info block as Markdown.

    Args:
        env: Environment dict from a bench result.

    Returns:
        Markdown string for the environment section.
    """
    lines: list[str] = ["## Environment", ""]
    field_labels = [
        ("os", "OS"),
        ("platform", "Platform"),
        ("python_version", "Python"),
        ("chimeraforge_version", "ChimeraForge"),
        ("gpu_name", "GPU"),
        ("gpu_driver", "GPU Driver"),
        ("cuda_version", "CUDA"),
        ("backend_name", "Backend"),
        ("backend_version", "Backend Version"),
    ]
    for key, label in field_labels:
        value = env.get(key)
        if value is not None:
            lines.append(f"- **{label}:** {value}")
    lines.append("")
    return "\n".join(lines)


def _md_summary_table(rows: list[BenchSummaryRow]) -> str:
    """Render the summary table as a Markdown table.

    Args:
        rows: Summary rows from ``summarize_bench_results``.

    Returns:
        GitHub-compatible Markdown table string.
    """
    lines: list[str] = [
        "## Summary",
        "",
        (
            "| Model | Backend | Quant | Workload | Context "
            "| Throughput (tok/s) | TTFT (ms) | Duration (ms) | Runs |"
        ),
        (
            "| ----- | ------- | ----- | -------- | ------- "
            "| -----------------: | --------: | ------------: | ---: |"
        ),
    ]
    for r in rows:
        lines.append(
            f"| {r.model} | {r.backend} | {r.quant} | {r.workload} "
            f"| {r.context_length} "
            f"| {r.throughput_mean:.1f} "
            f"| {r.ttft_mean:.1f} "
            f"| {r.duration_mean:.1f} "
            f"| {r.runs} |"
        )
    lines.append("")
    return "\n".join(lines)


def _md_detail_section(result: dict, index: int) -> str:
    """Render a per-config detail section as Markdown.

    Args:
        result: A single bench result dict.
        index: 1-based index for the section heading.

    Returns:
        Markdown string for one detailed result section.
    """
    model = result.get("model", "unknown")
    backend = result.get("backend", "unknown")
    quant = result.get("quant") or "default"
    ctx = result.get("context_length", 0)
    workload = result.get("workload", "single")

    heading = f"### {index}. {model} | {backend} | {quant} | ctx={ctx} | {workload}"
    lines: list[str] = [heading, ""]

    agg = result.get("aggregate", {})

    # Metrics table
    metrics = [
        ("throughput_tps", "Throughput (tok/s)"),
        ("ttft_ms", "TTFT (ms)"),
        ("total_duration_ms", "Total Duration (ms)"),
    ]
    lines.append("| Metric | Mean | P50 | P95 | P99 | Min | Max | StdDev |")
    lines.append("| ------ | ---: | --: | --: | --: | --: | --: | -----: |")

    for key, label in metrics:
        stat = agg.get(key, {})
        if not isinstance(stat, dict):
            stat = {}
        lines.append(
            f"| {label} "
            f"| {_fmt(stat.get('mean'))} "
            f"| {_fmt(stat.get('p50'))} "
            f"| {_fmt(stat.get('p95'))} "
            f"| {_fmt(stat.get('p99'))} "
            f"| {_fmt(stat.get('min'))} "
            f"| {_fmt(stat.get('max'))} "
            f"| {_fmt(stat.get('stddev'))} |"
        )
    lines.append("")

    count = agg.get("count", result.get("runs", 0))
    tokens = agg.get("tokens_generated", 0)
    lines.append(f"Runs: {count} | Total tokens: {tokens}")
    lines.append("")
    return "\n".join(lines)


def _fmt(value: float | None) -> str:
    """Format a numeric value for table display.

    Args:
        value: Numeric value or None.

    Returns:
        Formatted string with 1 decimal place, or ``"-"`` for None.
    """
    if value is None:
        return "-"
    return f"{value:.1f}"


def _md_warnings_section(results: list[dict]) -> str:
    """Collect and render all warnings as a Markdown section.

    Args:
        results: List of bench result dicts.

    Returns:
        Markdown string (empty string if no warnings).
    """
    all_warnings: list[str] = []
    for r in results:
        model = r.get("model", "unknown")
        quant = r.get("quant") or "default"
        for w in r.get("warnings", []):
            all_warnings.append(f"- **{model} ({quant}):** {w}")
    if not all_warnings:
        return ""
    lines = ["## Warnings", ""] + all_warnings + [""]
    return "\n".join(lines)


def generate_markdown(results: list[dict], config: ReportConfig) -> str:
    """Generate a Markdown report from bench results.

    Sections:
        1. Title + timestamp
        2. Environment info (from first result)
        3. Summary table (model | backend | quant | throughput | TTFT | duration | runs)
        4. Per-config detailed results
        5. Warnings (if any)

    Args:
        results: List of bench result dicts.
        config: Report configuration.

    Returns:
        Complete Markdown string.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    parts: list[str] = [
        f"# {config.title}",
        "",
        f"*Generated: {now}*",
        "",
    ]

    if not results:
        parts.append("No benchmark results to report.")
        parts.append("")
        return "\n".join(parts)

    # Environment
    if config.include_environment:
        env = results[0].get("environment", {})
        if env:
            parts.append(_md_environment_section(env))

    # Summary table
    rows = summarize_bench_results(results)
    parts.append(_md_summary_table(rows))

    # Detailed per-config sections
    parts.append("## Detailed Results")
    parts.append("")
    for i, r in enumerate(results, 1):
        parts.append(_md_detail_section(r, i))

    # Warnings
    if config.include_warnings:
        warnings_section = _md_warnings_section(results)
        if warnings_section:
            parts.append(warnings_section)

    # Footer
    parts.append("---")
    parts.append(f"*Report generated by ChimeraForge v{_get_version()}*")
    parts.append("")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# HTML generation
# ---------------------------------------------------------------------------

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                 "Helvetica Neue", Arial, sans-serif;
    line-height: 1.6;
    color: #24292e;
    max-width: 960px;
    margin: 0 auto;
    padding: 2rem;
    background: #fff;
  }}
  h1 {{ border-bottom: 2px solid #0366d6; padding-bottom: 0.3em; }}
  h2 {{ border-bottom: 1px solid #eaecef; padding-bottom: 0.3em; margin-top: 2em; }}
  h3 {{ margin-top: 1.5em; }}
  table {{
    border-collapse: collapse;
    width: 100%;
    margin: 1em 0;
  }}
  th, td {{
    border: 1px solid #dfe2e5;
    padding: 6px 13px;
    text-align: right;
  }}
  th {{
    background: #f6f8fa;
    font-weight: 600;
    text-align: right;
  }}
  th:first-child, td:first-child {{
    text-align: left;
  }}
  tr:nth-child(even) {{ background: #f6f8fa; }}
  .meta {{ color: #586069; font-style: italic; }}
  .warning {{ color: #856404; background: #fff3cd; padding: 0.5em; border-radius: 4px; }}
  ul {{ padding-left: 1.5em; }}
  hr {{ border: none; border-top: 1px solid #eaecef; margin: 2em 0; }}
  code {{ background: #f6f8fa; padding: 0.2em 0.4em; border-radius: 3px; }}
  .footer {{ color: #586069; font-size: 0.85em; margin-top: 2em; }}
</style>
</head>
<body>
{body}
</body>
</html>
"""


def _md_to_html_body(md: str) -> str:
    """Convert Markdown content to simple HTML.

    This is a lightweight converter that handles the subset of Markdown
    used by ``generate_markdown``: headings, tables, lists, emphasis,
    bold, italic, horizontal rules, and paragraphs.

    No external template engine or Markdown library is used.

    Args:
        md: Markdown source string.

    Returns:
        HTML body string.
    """
    lines = md.split("\n")
    html_parts: list[str] = []
    in_table = False
    in_list = False
    i = 0

    while i < len(lines):
        line = lines[i]

        # Blank line -- close any open list
        if not line.strip():
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            if in_table:
                html_parts.append("</tbody></table>")
                in_table = False
            i += 1
            continue

        # Horizontal rule
        if line.strip() == "---":
            if in_table:
                html_parts.append("</tbody></table>")
                in_table = False
            html_parts.append("<hr>")
            i += 1
            continue

        # Headings
        if line.startswith("###"):
            text = _inline_md(line.lstrip("#").strip())
            html_parts.append(f"<h3>{text}</h3>")
            i += 1
            continue
        if line.startswith("##"):
            text = _inline_md(line.lstrip("#").strip())
            html_parts.append(f"<h2>{text}</h2>")
            i += 1
            continue
        if line.startswith("# "):
            text = _inline_md(line.lstrip("#").strip())
            html_parts.append(f"<h1>{text}</h1>")
            i += 1
            continue

        # Table row
        if "|" in line and line.strip().startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            # Skip separator row (e.g. "| --- | --- |")
            if all(_is_separator_cell(c) for c in cells):
                i += 1
                continue
            if not in_table:
                in_table = True
                html_parts.append("<table><thead><tr>")
                for c in cells:
                    html_parts.append(f"<th>{_inline_md(c)}</th>")
                html_parts.append("</tr></thead><tbody>")
            else:
                html_parts.append("<tr>")
                for c in cells:
                    html_parts.append(f"<td>{_inline_md(c)}</td>")
                html_parts.append("</tr>")
            i += 1
            continue

        # Unordered list item
        if line.startswith("- "):
            if not in_list:
                in_list = True
                html_parts.append("<ul>")
            text = _inline_md(line[2:].strip())
            html_parts.append(f"<li>{text}</li>")
            i += 1
            continue

        # Italic-only line (e.g. *Generated: ...*)
        stripped = line.strip()
        if stripped.startswith("*") and stripped.endswith("*") and not stripped.startswith("**"):
            text = stripped[1:-1]
            html_parts.append(f'<p class="meta">{_inline_md(text)}</p>')
            i += 1
            continue

        # Regular paragraph
        html_parts.append(f"<p>{_inline_md(line)}</p>")
        i += 1

    # Close any dangling structures
    if in_list:
        html_parts.append("</ul>")
    if in_table:
        html_parts.append("</tbody></table>")

    return "\n".join(html_parts)


def _is_separator_cell(cell: str) -> bool:
    """Check if a table cell is a Markdown separator (e.g. ``---``, ``:---:``).

    Args:
        cell: Cell content string.

    Returns:
        True if the cell is a separator.
    """
    cleaned = cell.strip().strip(":")
    return len(cleaned) > 0 and all(c == "-" for c in cleaned)


def _html_escape(text: str) -> str:
    """Escape HTML special characters.

    Args:
        text: Raw text.

    Returns:
        Text safe for insertion into HTML.
    """
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )


def _inline_md(text: str) -> str:
    """Convert inline Markdown (bold, italic, code) to HTML.

    Handles ``**bold**``, ``*italic*``, and `` `code` `` patterns.
    HTML-escapes all content first to prevent injection.

    Args:
        text: Inline Markdown text.

    Returns:
        HTML string with inline formatting applied.
    """
    result: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        # Bold: **text**
        if i < n - 1 and text[i : i + 2] == "**":
            end = text.find("**", i + 2)
            if end != -1:
                result.append(f"<strong>{_html_escape(text[i + 2 : end])}</strong>")
                i = end + 2
                continue
        # Code: `text`
        if text[i] == "`":
            end = text.find("`", i + 1)
            if end != -1:
                result.append(f"<code>{_html_escape(text[i + 1 : end])}</code>")
                i = end + 1
                continue
        # Italic: *text*
        if text[i] == "*" and (i == 0 or text[i - 1] != "*"):
            end = text.find("*", i + 1)
            if end != -1 and (end + 1 >= n or text[end + 1] != "*"):
                result.append(f"<em>{_html_escape(text[i + 1 : end])}</em>")
                i = end + 1
                continue
        result.append(_html_escape(text[i]))
        i += 1
    return "".join(result)


def generate_html(results: list[dict], config: ReportConfig) -> str:
    """Generate an HTML report from bench results.

    Wraps Markdown content in a self-contained HTML template with inline
    CSS.  Does **not** require any template engine -- uses string formatting.

    Args:
        results: List of bench result dicts.
        config: Report configuration.

    Returns:
        Complete HTML string.
    """
    md = generate_markdown(results, config)
    body = _md_to_html_body(md)
    return _HTML_TEMPLATE.format(title=config.title, body=body)


# ---------------------------------------------------------------------------
# Top-level API
# ---------------------------------------------------------------------------


def generate_report(
    result_paths: list[Path],
    config: ReportConfig | None = None,
) -> Report:
    """Top-level report generator.

    Loads bench result JSON files and generates a report in the configured
    format (Markdown or HTML).

    Args:
        result_paths: Paths to bench result JSON files.
        config: Report configuration. Uses defaults if ``None``.

    Returns:
        A ``Report`` dataclass containing the rendered content.
    """
    if config is None:
        config = ReportConfig()

    results = load_results(result_paths)

    if config.format == "html":
        content = generate_html(results, config)
    else:
        content = generate_markdown(results, config)

    return Report(
        title=config.title,
        format=config.format,
        content=content,
        timestamp=datetime.now(timezone.utc).isoformat(),
        n_results=len(results),
    )


def save_report(report: Report, output_path: Path) -> Path:
    """Write a report to a file.

    Creates parent directories if they do not exist.

    Args:
        report: The generated report.
        output_path: Destination file path.

    Returns:
        The resolved output path.
    """
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report.content, encoding="utf-8")
    return output_path


def format_report_rich(results: list[dict], console: Console) -> None:
    """Print a Rich-formatted summary to the console.

    This mirrors the output style of ``chimeraforge bench`` but works
    from loaded result dicts rather than live ``BenchmarkResult`` objects.

    Args:
        results: List of bench result dicts.
        console: A ``rich.console.Console`` instance.
    """
    from rich.panel import Panel
    from rich.table import Table

    if not results:
        console.print(
            Panel(
                "[bold yellow]No benchmark results to display.[/]",
                title="ChimeraForge Report",
                border_style="yellow",
            )
        )
        return

    rows = summarize_bench_results(results)

    # Summary table
    summary = Table(title="Benchmark Summary", show_header=True, header_style="bold cyan")
    summary.add_column("Model", style="bold")
    summary.add_column("Backend")
    summary.add_column("Quant")
    summary.add_column("Workload")
    summary.add_column("Context", justify="right")
    summary.add_column("Throughput (tok/s)", justify="right")
    summary.add_column("TTFT (ms)", justify="right")
    summary.add_column("Duration (ms)", justify="right")
    summary.add_column("Runs", justify="right")

    for r in rows:
        summary.add_row(
            r.model,
            r.backend,
            r.quant,
            r.workload,
            str(r.context_length),
            f"{r.throughput_mean:.1f}",
            f"{r.ttft_mean:.1f}",
            f"{r.duration_mean:.1f}",
            str(r.runs),
        )

    console.print()
    console.print(summary)
    # Per-config detail tables
    for result in results:
        agg = result.get("aggregate", {})
        model = result.get("model", "unknown")
        backend = result.get("backend", "unknown")
        quant = result.get("quant") or "default"
        ctx = result.get("context_length", 0)
        title = f"{model} | {backend} | {quant} | ctx={ctx}"

        detail = Table(title=title, show_header=True, header_style="bold cyan")
        detail.add_column("Metric", style="bold")
        detail.add_column("Mean", justify="right")
        detail.add_column("P50", justify="right")
        detail.add_column("P95", justify="right")
        detail.add_column("P99", justify="right")
        detail.add_column("StdDev", justify="right")

        for key, label in [
            ("throughput_tps", "Throughput (tok/s)"),
            ("ttft_ms", "TTFT (ms)"),
            ("total_duration_ms", "Total Duration (ms)"),
        ]:
            stat = agg.get(key, {})
            if not isinstance(stat, dict):
                stat = {}
            detail.add_row(
                label,
                _fmt(stat.get("mean")),
                _fmt(stat.get("p50")),
                _fmt(stat.get("p95")),
                _fmt(stat.get("p99")),
                _fmt(stat.get("stddev")),
            )

        console.print()
        console.print(detail)
        count = agg.get("count", result.get("runs", 0))
        tokens = agg.get("tokens_generated", 0)
        console.print(
            f"  [dim]Runs: {count} | Total tokens: {tokens} "
            f"| Workload: {result.get('workload', 'single')}[/dim]"
        )

        warnings = result.get("warnings", [])
        if warnings:
            for w in warnings:
                console.print(f"  [yellow]Warning:[/] {w}")
    # Environment info from first result
    env = results[0].get("environment", {})
    if env:
        env_parts: list[str] = []
        if env.get("gpu_name"):
            env_parts.append(f"GPU: {env['gpu_name']}")
        if env.get("os"):
            env_parts.append(f"OS: {env['os']}")
        if env.get("python_version"):
            env_parts.append(f"Python: {env['python_version']}")
        if env_parts:
            console.print(f"\n  [dim]{' | '.join(env_parts)}[/dim]")

    console.print(f"\n  [dim]{len(results)} result(s) reported[/dim]\n")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_version() -> str:
    """Get the ChimeraForge version string.

    Returns:
        Version string, or ``"unknown"`` if the package is not installed.
    """
    try:
        import chimeraforge

        return chimeraforge.__version__
    except (ImportError, AttributeError):
        return "unknown"
