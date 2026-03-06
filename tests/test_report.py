"""ChimeraForge Report — unit tests.

Tests statistical analysis, report generation (Markdown, HTML, Rich),
loading, saving, and CLI integration.

Run:
    pytest tests/test_report.py -v
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

from helpers import make_result as _make_result, write_bench_json as _write_bench_json


# ---------------------------------------------------------------------------
# TestAnalysisStats
# ---------------------------------------------------------------------------


class TestAnalysisStats:
    def test_rmse_perfect(self):
        from chimeraforge.report.analysis import compute_rmse

        assert compute_rmse([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == 0.0

    def test_rmse_nonzero(self):
        from chimeraforge.report.analysis import compute_rmse

        result = compute_rmse([1.0, 2.0], [2.0, 3.0])
        assert result == pytest.approx(1.0)

    def test_mae(self):
        from chimeraforge.report.analysis import compute_mae

        assert compute_mae([1.0, 3.0], [2.0, 4.0]) == pytest.approx(1.0)

    def test_mape(self):
        from chimeraforge.report.analysis import compute_mape

        # |1-2|/1 = 1.0, |2-3|/2 = 0.5 -> mean = 0.75
        assert compute_mape([1.0, 2.0], [2.0, 3.0]) == pytest.approx(0.75)

    def test_mape_skips_zero_actual(self):
        from chimeraforge.report.analysis import compute_mape

        # zero actual skipped, only (2.0-3.0)/2.0 = 0.5
        assert compute_mape([0.0, 2.0], [1.0, 3.0]) == pytest.approx(0.5)

    def test_r_squared_perfect(self):
        from chimeraforge.report.analysis import compute_r_squared

        assert compute_r_squared([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == pytest.approx(1.0)

    def test_r_squared_bad(self):
        from chimeraforge.report.analysis import compute_r_squared

        r2 = compute_r_squared([1.0, 2.0, 3.0], [3.0, 2.0, 1.0])
        assert r2 < 0.5

    def test_analyze_all(self):
        from chimeraforge.report.analysis import analyze

        stats = analyze([1.0, 2.0, 3.0], [1.0, 2.0, 3.0])
        assert stats.rmse == 0.0
        assert stats.r_squared == pytest.approx(1.0)
        assert stats.n_samples == 3

    def test_length_mismatch_raises(self):
        from chimeraforge.report.analysis import compute_rmse

        with pytest.raises(ValueError, match="Length mismatch"):
            compute_rmse([1.0], [1.0, 2.0])

    def test_empty_returns_zero(self):
        from chimeraforge.report.analysis import compute_rmse

        assert compute_rmse([], []) == 0.0


# ---------------------------------------------------------------------------
# TestBenchSummaryRow
# ---------------------------------------------------------------------------


class TestBenchSummaryRow:
    def test_summarize_single_result(self):
        from chimeraforge.report.analysis import summarize_bench_results

        rows = summarize_bench_results([_make_result()])
        assert len(rows) == 1
        assert rows[0].model == "llama3.2-3b"
        assert rows[0].throughput_mean == 95.0

    def test_summarize_sorted_by_model_quant(self):
        from chimeraforge.report.analysis import summarize_bench_results

        results = [
            _make_result(model="b"),
            _make_result(model="a"),
        ]
        rows = summarize_bench_results(results)
        assert rows[0].model == "a"
        assert rows[1].model == "b"


# ---------------------------------------------------------------------------
# TestGenerateMarkdown
# ---------------------------------------------------------------------------


class TestGenerateMarkdown:
    def test_contains_title(self):
        from chimeraforge.report.generator import ReportConfig, generate_markdown

        md = generate_markdown([_make_result()], ReportConfig(title="Test Report"))
        assert "# Test Report" in md

    def test_contains_summary_table(self):
        from chimeraforge.report.generator import ReportConfig, generate_markdown

        md = generate_markdown([_make_result()], ReportConfig())
        assert "## Summary" in md
        assert "llama3.2-3b" in md

    def test_empty_results(self):
        from chimeraforge.report.generator import ReportConfig, generate_markdown

        md = generate_markdown([], ReportConfig())
        assert "No benchmark results" in md

    def test_includes_environment(self):
        from chimeraforge.report.generator import ReportConfig, generate_markdown

        md = generate_markdown([_make_result()], ReportConfig(include_environment=True))
        assert "RTX 4080" in md

    def test_includes_warnings(self):
        from chimeraforge.report.generator import ReportConfig, generate_markdown

        r = _make_result()
        r["warnings"] = ["test warning"]
        md = generate_markdown([r], ReportConfig(include_warnings=True))
        assert "test warning" in md


# ---------------------------------------------------------------------------
# TestGenerateHTML
# ---------------------------------------------------------------------------


class TestGenerateHTML:
    def test_contains_html_structure(self):
        from chimeraforge.report.generator import ReportConfig, generate_html

        html = generate_html([_make_result()], ReportConfig())
        assert "<!DOCTYPE html>" in html
        assert "<table>" in html
        assert "llama3.2-3b" in html

    def test_empty_results(self):
        from chimeraforge.report.generator import ReportConfig, generate_html

        html = generate_html([], ReportConfig())
        assert "No benchmark results" in html

    def test_html_escapes_special_chars(self):
        from chimeraforge.report.generator import ReportConfig, generate_html

        r = _make_result(model='<script>alert("xss")</script>')
        html = generate_html([r], ReportConfig())
        assert "<script>" not in html
        assert "&lt;script&gt;" in html


# ---------------------------------------------------------------------------
# TestGenerateReport
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_markdown_format(self, tmp_path: Path):
        from chimeraforge.report.generator import ReportConfig, generate_report

        f = tmp_path / "bench.json"
        _write_bench_json(f, [_make_result()])
        rpt = generate_report([f], ReportConfig(format="markdown"))
        assert rpt.format == "markdown"
        assert "## Summary" in rpt.content
        assert rpt.n_results == 1

    def test_html_format(self, tmp_path: Path):
        from chimeraforge.report.generator import ReportConfig, generate_report

        f = tmp_path / "bench.json"
        _write_bench_json(f, [_make_result()])
        rpt = generate_report([f], ReportConfig(format="html"))
        assert rpt.format == "html"
        assert "<!DOCTYPE html>" in rpt.content


# ---------------------------------------------------------------------------
# TestSaveReport
# ---------------------------------------------------------------------------


class TestSaveReport:
    def test_save_and_read(self, tmp_path: Path):
        from chimeraforge.report.generator import Report, save_report

        rpt = Report(
            title="Test",
            format="markdown",
            content="# Test\n\nHello",
            timestamp="2026-01-01",
            n_results=1,
        )
        out = tmp_path / "sub" / "report.md"
        saved = save_report(rpt, out)
        assert saved.exists()
        assert saved.read_text() == "# Test\n\nHello"


# ---------------------------------------------------------------------------
# TestLoadResults
# ---------------------------------------------------------------------------


class TestLoadResults:
    def test_load_list(self, tmp_path: Path):
        from chimeraforge.report.generator import load_results

        f = tmp_path / "bench.json"
        _write_bench_json(f, [_make_result(), _make_result(model="b")])
        results = load_results([f])
        assert len(results) == 2

    def test_load_single_dict(self, tmp_path: Path):
        from chimeraforge.report.generator import load_results

        f = tmp_path / "bench.json"
        f.write_text(json.dumps(_make_result()))
        results = load_results([f])
        assert len(results) == 1


# ---------------------------------------------------------------------------
# TestFormatReportRich
# ---------------------------------------------------------------------------


class TestFormatReportRich:
    def test_non_empty(self, tmp_path: Path):
        from rich.console import Console

        from chimeraforge.report.generator import format_report_rich

        c = Console(file=open(tmp_path / "out.txt", "w"), force_terminal=False)
        format_report_rich([_make_result()], c)

    def test_empty(self, tmp_path: Path):
        from rich.console import Console

        from chimeraforge.report.generator import format_report_rich

        c = Console(file=open(tmp_path / "out.txt", "w"), force_terminal=False)
        format_report_rich([], c)


# ---------------------------------------------------------------------------
# TestCLIReport
# ---------------------------------------------------------------------------


class TestCLIReport:
    @staticmethod
    def _strip_ansi(text: str) -> str:
        import re

        return re.sub(r"\x1b\[[0-9;]*m", "", text)

    def test_report_help(self):
        from typer.testing import CliRunner

        from chimeraforge.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["report", "--help"])
        output = self._strip_ansi(result.output)
        assert result.exit_code == 0
        assert "--results-dir" in output

    def test_report_no_input_exits_1(self):
        from typer.testing import CliRunner

        from chimeraforge.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["report"])
        assert result.exit_code == 1

    def test_report_with_file(self, tmp_path: Path):
        from typer.testing import CliRunner

        from chimeraforge.cli import app

        f = tmp_path / "bench.json"
        _write_bench_json(f, [_make_result()])
        out = tmp_path / "report.md"

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "report",
                "--results-files",
                str(f),
                "--output",
                str(out),
            ],
        )
        assert result.exit_code == 0
        assert out.exists()

    def test_report_html_format(self, tmp_path: Path):
        from typer.testing import CliRunner

        from chimeraforge.cli import app

        f = tmp_path / "bench.json"
        _write_bench_json(f, [_make_result()])
        out = tmp_path / "report.html"

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "report",
                "--results-files",
                str(f),
                "--format",
                "html",
                "--output",
                str(out),
            ],
        )
        assert result.exit_code == 0
        assert "<!DOCTYPE html>" in out.read_text()

    def test_report_invalid_format(self, tmp_path: Path):
        from typer.testing import CliRunner

        from chimeraforge.cli import app

        f = tmp_path / "bench.json"
        _write_bench_json(f, [_make_result()])

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "report",
                "--results-files",
                str(f),
                "--format",
                "pdf",
            ],
        )
        assert result.exit_code == 1
