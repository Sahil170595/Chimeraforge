"""ChimeraForge Compare — unit tests.

Tests the compare pipeline: key generation, grouping, delta calculation,
Rich table formatting, JSON output, and CLI integration.

Run:
    pytest tests/test_compare.py -v
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rich.console import Console


# ---------------------------------------------------------------------------
# Helpers — synthetic bench result dicts
# ---------------------------------------------------------------------------


def _make_result(
    model: str = "llama3.2-3b",
    backend: str = "ollama",
    quant: str | None = None,
    throughput_mean: float = 95.0,
    ttft_mean: float = 50.0,
    duration_mean: float = 1000.0,
    runs: int = 5,
    workload: str = "single",
    context_length: int = 2048,
) -> dict:
    return {
        "model": model,
        "backend": backend,
        "quant": quant,
        "workload": workload,
        "context_length": context_length,
        "runs": runs,
        "aggregate": {
            "count": runs,
            "throughput_tps": {"mean": throughput_mean, "p50": throughput_mean, "p95": throughput_mean, "p99": throughput_mean, "min": throughput_mean, "max": throughput_mean, "stddev": 0.5},
            "ttft_ms": {"mean": ttft_mean, "p50": ttft_mean, "p95": ttft_mean, "p99": ttft_mean, "min": ttft_mean, "max": ttft_mean, "stddev": 1.0},
            "total_duration_ms": {"mean": duration_mean, "p50": duration_mean, "p95": duration_mean, "p99": duration_mean, "min": duration_mean, "max": duration_mean, "stddev": 10.0},
            "tokens_generated": 640,
        },
        "individual_runs": [],
        "environment": {},
        "timestamp": "2026-01-01T00:00:00+00:00",
        "warnings": [],
    }


def _write_bench_json(path: Path, results: list[dict]) -> None:
    path.write_text(json.dumps(results, indent=2))


# ---------------------------------------------------------------------------
# TestMakeKey
# ---------------------------------------------------------------------------


class TestMakeKey:
    def test_standard_result(self):
        from chimeraforge.compare.comparator import make_key

        r = _make_result(model="m", backend="b", quant="Q4_K_M", workload="single", context_length=2048)
        assert make_key(r) == "m|b|Q4_K_M|single|2048"

    def test_none_quant_uses_default(self):
        from chimeraforge.compare.comparator import make_key

        r = _make_result(quant=None)
        key = make_key(r)
        assert "|default|" in key


# ---------------------------------------------------------------------------
# TestGroupByKey
# ---------------------------------------------------------------------------


class TestGroupByKey:
    def test_same_config_grouped(self):
        from chimeraforge.compare.comparator import group_by_key

        r1 = _make_result(model="m", backend="b")
        r2 = _make_result(model="m", backend="b")
        groups = group_by_key([r1, r2])
        assert len(groups) == 1
        key = list(groups.keys())[0]
        assert len(groups[key]) == 2

    def test_different_configs_separate(self):
        from chimeraforge.compare.comparator import group_by_key

        r1 = _make_result(model="a")
        r2 = _make_result(model="b")
        groups = group_by_key([r1, r2])
        assert len(groups) == 2


# ---------------------------------------------------------------------------
# TestCompareResults
# ---------------------------------------------------------------------------


class TestCompareResults:
    def test_matching_configs(self, tmp_path: Path):
        from chimeraforge.compare.comparator import compare_results

        base = tmp_path / "base.json"
        cand = tmp_path / "cand.json"
        _write_bench_json(base, [_make_result(throughput_mean=40.0)])
        _write_bench_json(cand, [_make_result(throughput_mean=50.0)])

        rows = compare_results(base, [cand])
        assert len(rows) == 1
        assert rows[0].baseline_throughput == 40.0
        assert rows[0].candidate_throughput == 50.0

    def test_no_matching_configs(self, tmp_path: Path):
        from chimeraforge.compare.comparator import compare_results

        base = tmp_path / "base.json"
        cand = tmp_path / "cand.json"
        _write_bench_json(base, [_make_result(model="a")])
        _write_bench_json(cand, [_make_result(model="b")])

        rows = compare_results(base, [cand])
        assert len(rows) == 0

    def test_throughput_improvement(self, tmp_path: Path):
        from chimeraforge.compare.comparator import compare_results

        base = tmp_path / "base.json"
        cand = tmp_path / "cand.json"
        _write_bench_json(base, [_make_result(throughput_mean=40.0)])
        _write_bench_json(cand, [_make_result(throughput_mean=50.0)])

        rows = compare_results(base, [cand])
        assert rows[0].delta_throughput_pct == pytest.approx(25.0)

    def test_throughput_regression(self, tmp_path: Path):
        from chimeraforge.compare.comparator import compare_results

        base = tmp_path / "base.json"
        cand = tmp_path / "cand.json"
        _write_bench_json(base, [_make_result(throughput_mean=50.0)])
        _write_bench_json(cand, [_make_result(throughput_mean=40.0)])

        rows = compare_results(base, [cand])
        assert rows[0].delta_throughput_pct == pytest.approx(-20.0)

    def test_multiple_configs(self, tmp_path: Path):
        from chimeraforge.compare.comparator import compare_results

        base = tmp_path / "base.json"
        cand = tmp_path / "cand.json"
        _write_bench_json(base, [
            _make_result(model="a", throughput_mean=40.0),
            _make_result(model="b", throughput_mean=80.0),
        ])
        _write_bench_json(cand, [
            _make_result(model="a", throughput_mean=50.0),
            _make_result(model="b", throughput_mean=60.0),
        ])

        rows = compare_results(base, [cand])
        assert len(rows) == 2


# ---------------------------------------------------------------------------
# TestComparisonRow
# ---------------------------------------------------------------------------


class TestComparisonRow:
    def test_delta_calculation(self):
        from chimeraforge.compare.comparator import _safe_delta_pct

        assert _safe_delta_pct(40.0, 50.0) == pytest.approx(25.0)

    def test_zero_baseline(self):
        from chimeraforge.compare.comparator import _safe_delta_pct

        assert _safe_delta_pct(0.0, 50.0) == 0.0


# ---------------------------------------------------------------------------
# TestFormatComparisonTable
# ---------------------------------------------------------------------------


class TestFormatComparisonTable:
    def test_non_empty_rows(self, tmp_path: Path):
        from chimeraforge.compare.comparator import compare_results, format_comparison_table

        base = tmp_path / "base.json"
        cand = tmp_path / "cand.json"
        _write_bench_json(base, [_make_result(throughput_mean=40.0)])
        _write_bench_json(cand, [_make_result(throughput_mean=50.0)])

        rows = compare_results(base, [cand])
        c = Console(file=open(tmp_path / "out.txt", "w"), force_terminal=False)
        format_comparison_table(rows, c)
        # No exception is success

    def test_empty_rows(self, tmp_path: Path):
        from chimeraforge.compare.comparator import format_comparison_table

        c = Console(file=open(tmp_path / "out.txt", "w"), force_terminal=False)
        format_comparison_table([], c)
        # Should print "No matching configurations" without error


# ---------------------------------------------------------------------------
# TestFormatComparisonJson
# ---------------------------------------------------------------------------


class TestFormatComparisonJson:
    def test_round_trip(self, tmp_path: Path):
        from chimeraforge.compare.comparator import compare_results, format_comparison_json

        base = tmp_path / "base.json"
        cand = tmp_path / "cand.json"
        _write_bench_json(base, [_make_result(throughput_mean=40.0)])
        _write_bench_json(cand, [_make_result(throughput_mean=50.0)])

        rows = compare_results(base, [cand])
        j = format_comparison_json(rows)
        parsed = json.loads(j)
        assert len(parsed) == 1
        assert parsed[0]["baseline_throughput"] == 40.0
        assert parsed[0]["candidate_throughput"] == 50.0
        assert parsed[0]["delta_throughput_pct"] == pytest.approx(25.0)

    def test_empty_rows(self):
        from chimeraforge.compare.comparator import format_comparison_json

        j = format_comparison_json([])
        assert json.loads(j) == []


# ---------------------------------------------------------------------------
# TestFormatComparisonSummary
# ---------------------------------------------------------------------------


class TestFormatComparisonSummary:
    def test_non_empty(self, tmp_path: Path):
        from chimeraforge.compare.comparator import compare_results, format_comparison_summary

        base = tmp_path / "base.json"
        cand = tmp_path / "cand.json"
        _write_bench_json(base, [_make_result(throughput_mean=40.0)])
        _write_bench_json(cand, [_make_result(throughput_mean=50.0)])

        rows = compare_results(base, [cand])
        c = Console(file=open(tmp_path / "out.txt", "w"), force_terminal=False)
        format_comparison_summary(rows, c)

    def test_empty(self, tmp_path: Path):
        from chimeraforge.compare.comparator import format_comparison_summary

        c = Console(file=open(tmp_path / "out.txt", "w"), force_terminal=False)
        format_comparison_summary([], c)


# ---------------------------------------------------------------------------
# TestCLICompare
# ---------------------------------------------------------------------------


class TestCLICompare:
    @staticmethod
    def _strip_ansi(text: str) -> str:
        import re

        return re.sub(r"\x1b\[[0-9;]*m", "", text)

    def test_compare_help(self):
        from typer.testing import CliRunner

        from chimeraforge.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["compare", "--help"])
        output = self._strip_ansi(result.output)
        assert result.exit_code == 0
        assert "--baseline" in output

    def test_compare_missing_baseline_exits_1(self, tmp_path: Path):
        from typer.testing import CliRunner

        from chimeraforge.cli import app

        runner = CliRunner()
        result = runner.invoke(app, [
            "compare",
            "--baseline", str(tmp_path / "nope.json"),
            "--candidate", str(tmp_path / "also_nope.json"),
        ])
        assert result.exit_code == 1

    def test_compare_valid_files(self, tmp_path: Path):
        from typer.testing import CliRunner

        from chimeraforge.cli import app

        base = tmp_path / "base.json"
        cand = tmp_path / "cand.json"
        _write_bench_json(base, [_make_result(throughput_mean=40.0)])
        _write_bench_json(cand, [_make_result(throughput_mean=50.0)])

        runner = CliRunner()
        result = runner.invoke(app, [
            "compare",
            "--baseline", str(base),
            "--candidate", str(cand),
        ])
        assert result.exit_code == 0
