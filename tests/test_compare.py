"""ChimeraForge Compare - unit tests.

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

from helpers import make_result as _make_result, write_bench_json as _write_bench_json


# ---------------------------------------------------------------------------
# TestMakeKey
# ---------------------------------------------------------------------------


class TestMakeKey:
    def test_standard_result(self):
        from chimeraforge.compare.comparator import make_key

        r = _make_result(
            model="m", backend="b", quant="Q4_K_M", workload="single", context_length=2048
        )
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
    def test_mixed_native_ttft_samples_stay_unavailable(self, tmp_path: Path):
        from dataclasses import asdict

        from chimeraforge.bench.metrics import RunMetrics, aggregate_runs
        from chimeraforge.compare import compare_results

        base, cand = tmp_path / "base.json", tmp_path / "cand.json"
        for path, ttfts in ((base, [100, 100]), (cand, [-1, 100])):
            row = _make_result()
            aggregate = aggregate_runs([RunMetrics(10, 40, ttft, 500, 0, 250) for ttft in ttfts])
            row["aggregate"] = asdict(aggregate)
            _write_bench_json(path, [row])
        comparison = compare_results(base, [cand])[0]
        assert comparison.baseline_ttft == 100
        assert comparison.candidate_ttft is None and comparison.delta_ttft_pct is None
        assert comparison.delta_throughput_pct == 0.0

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
        _write_bench_json(
            base,
            [
                _make_result(model="a", throughput_mean=40.0),
                _make_result(model="b", throughput_mean=80.0),
            ],
        )
        _write_bench_json(
            cand,
            [
                _make_result(model="a", throughput_mean=50.0),
                _make_result(model="b", throughput_mean=60.0),
            ],
        )

        rows = compare_results(base, [cand])
        assert len(rows) == 2


# ---------------------------------------------------------------------------
# TestComparisonRow
# ---------------------------------------------------------------------------


class TestComparisonRow:
    def test_delta_calculation(self):
        from chimeraforge.compare.comparator import _safe_delta_pct

        assert _safe_delta_pct(40.0, 50.0) == pytest.approx(25.0)

    def test_zero_baseline_is_undefined_not_no_change(self):
        """0 -> 50 is an unbounded regression, not a flat line. Returning 0.0 made
        the table render it dim as "no change"."""
        from chimeraforge.compare.comparator import _safe_delta_pct

        assert _safe_delta_pct(0.0, 50.0) is None

    def test_negative_baseline_is_undefined(self):
        """The only source of a negative baseline is the -1.0 "not measurable"
        TTFT sentinel, which produced -85,100% rendered GREEN as an improvement."""
        from chimeraforge.compare.comparator import _safe_delta_pct

        assert _safe_delta_pct(-1.0, 850.0) is None

    def test_missing_candidate_is_undefined_but_measured_zero_is_retained(self):
        from chimeraforge.compare.comparator import _safe_delta_pct

        assert _safe_delta_pct(100.0, -1.0) is None
        assert _safe_delta_pct(100.0, float("nan")) is None
        assert _safe_delta_pct(100.0, 0.0) == -100.0

    def test_an_undefined_delta_renders_as_na(self):
        from chimeraforge.compare.comparator import _delta_style

        assert "n/a" in _delta_style(None)
        assert "%" not in _delta_style(None)

    def test_aggregate_is_a_ratio_of_totals_not_a_mean_of_percentages(self):
        """100->50 paired with 50->100 is no net change. The mean of -50% and
        +100% is +25%, which the summary rendered green."""
        from chimeraforge.compare.comparator import _ratio_delta_pct

        assert _ratio_delta_pct(150.0, 150.0) == pytest.approx(0.0)
        assert _ratio_delta_pct(0.0, 10.0) is None


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
    def test_totals_use_only_comparable_pairs(self, tmp_path: Path):
        from io import StringIO

        from chimeraforge.compare import compare_results, format_comparison_summary

        base, cand = tmp_path / "base.json", tmp_path / "cand.json"
        _write_bench_json(
            base,
            [
                _make_result(model="a", throughput_mean=40),
                _make_result(model="b", throughput_mean=0),
            ],
        )
        _write_bench_json(
            cand,
            [
                _make_result(model="a", throughput_mean=50),
                _make_result(model="b", throughput_mean=1000),
            ],
        )
        out = StringIO()
        format_comparison_summary(compare_results(base, [cand]), Console(file=out, width=100))
        assert "Total throughput delta: +25.0%" in out.getvalue()

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
    def test_each_candidate_keeps_its_rows_and_missing_configurations(self, tmp_path: Path):
        from typer.testing import CliRunner

        from chimeraforge.cli import app
        from chimeraforge.compare import compare_results, make_key

        base, first, second, no_match = [
            tmp_path / name for name in ("base", "[first]", "second", "other")
        ]
        row = _make_result(model="shared", throughput_mean=40, ttft_mean=100)
        base_only, candidate_only = (
            _make_result(model="base-only"),
            _make_result(model="candidate-only"),
        )
        _write_bench_json(base, [row, base_only])
        _write_bench_json(first, [_make_result(model="shared", throughput_mean=50, ttft_mean=-1)])
        _write_bench_json(second, [_make_result(model="shared", throughput_mean=20, ttft_mean=200)])
        _write_bench_json(no_match, [candidate_only])
        runner = CliRunner()
        command = ["compare", "--baseline", str(base), "--candidate"]
        arguments = [*command, f"{first},{second},{no_match}"]
        flat = runner.invoke(app, [*arguments, "--json"])
        assert flat.exit_code == 0, flat.output
        flat_rows = json.loads(flat.stdout)
        assert isinstance(flat_rows, list)
        assert [row["candidate_throughput"] for row in flat_rows] == [50.0, 20.0]

        result = runner.invoke(app, [*arguments, "--grouped-json"])
        assert result.exit_code == 0, result.output
        report = json.loads(result.stdout)
        assert report["schema_version"] == 1 and report["baseline"] == str(base)
        candidates = report["candidates"]
        assert [value["candidate"] for value in candidates] == [
            str(first),
            str(second),
            str(no_match),
        ]
        assert [value["rows"][0]["delta_throughput_pct"] for value in candidates[:2]] == [
            25.0,
            -50.0,
        ]
        assert candidates[0]["rows"][0]["delta_ttft_pct"] is None
        assert candidates[0]["rows"][0]["candidate_ttft"] is None
        assert candidates[1]["rows"][0]["delta_ttft_pct"] == 100.0
        assert candidates[2] == {
            "candidate": str(no_match),
            "rows": [],
            "baseline_only": [make_key(row), make_key(base_only)],
            "candidate_only": [make_key(candidate_only)],
        }
        assert candidates[0]["baseline_only"] == [make_key(base_only)]
        assert [row.candidate_throughput for row in compare_results(base, [first, second])] == [
            50,
            20,
        ]
        expected_flat = [dict(row) for candidate in candidates for row in candidate["rows"]]
        expected_flat[0]["candidate_ttft"] = -1.0
        assert flat_rows == expected_flat
        single = runner.invoke(app, [*command, str(first), "--json"])
        assert single.exit_code == 0, single.output
        assert json.loads(single.stdout) == expected_flat[:1]
        single_group = runner.invoke(app, [*command, str(first), "--grouped-json"])
        assert single_group.exit_code == 0, single_group.output
        assert json.loads(single_group.stdout)["candidates"] == [candidates[0]]
        no_rows = runner.invoke(app, [*command, str(no_match), "--json"])
        assert no_rows.exit_code == 0, no_rows.output
        assert json.loads(no_rows.stdout) == []

        conflicting = runner.invoke(app, [*arguments, "--json", "--grouped-json"])
        assert conflicting.exit_code == 1
        assert not conflicting.stdout and "mutually exclusive" in conflicting.stderr

    @pytest.mark.parametrize(
        "baseline,throughput,limit,missing,expected",
        [
            (50, 45, "10", False, 0),
            (50, 44, "10", False, 3),
            (50, 44, "10", True, 3),
            (50, 45, "10", True, 4),
            (50, -1, "10", False, 4),
            (100, 45, "55", False, 0),
            (100, 44.99999999999999, "55", False, 3),
        ],
    )
    def test_throughput_gate_retains_grouped_report(
        self, tmp_path, baseline, throughput, limit, missing, expected
    ):
        from typer.testing import CliRunner

        from chimeraforge.cli import app

        base, cand = tmp_path / "base.json", tmp_path / "cand.json"
        rows = [_make_result(throughput_mean=baseline)]
        if missing:
            rows.append(_make_result(model="missing"))
        _write_bench_json(base, rows)
        _write_bench_json(
            cand, [_make_result(throughput_mean=throughput), _make_result(model="new")]
        )
        result = CliRunner().invoke(
            app,
            [
                "compare",
                "--baseline",
                str(base),
                "--candidate",
                str(cand),
                "--grouped-json",
                "--max-throughput-regression-pct",
                limit,
            ],
        )
        assert result.exit_code == expected, result.output
        report = json.loads(result.stdout)
        assert len(report["candidates"][0]["rows"]) == 1
        assert report["candidates"][0]["candidate_only"]
        assert bool(result.stderr) == (expected != 0)

    def test_nonfinite_throughput_gate_is_rejected_before_inputs(self):
        from typer.testing import CliRunner

        from chimeraforge.cli import app

        result = CliRunner().invoke(
            app,
            [
                "compare",
                "--baseline",
                "absent",
                "--candidate",
                "absent",
                "--max-throughput-regression-pct",
                "nan",
            ],
        )
        assert result.exit_code == 1
        assert "finite percentage" in result.stderr

    @pytest.mark.parametrize("side", ["baseline", "candidate"])
    def test_duplicate_configuration_is_rejected(self, tmp_path: Path, side: str):
        from typer.testing import CliRunner

        from chimeraforge.cli import app

        base, cand = tmp_path / "base.json", tmp_path / "cand.json"
        _write_bench_json(base, [_make_result()] * (2 if side == "baseline" else 1))
        _write_bench_json(cand, [_make_result()] * (2 if side == "candidate" else 1))
        result = CliRunner().invoke(
            app, ["compare", "--baseline", str(base), "--candidate", str(cand), "--json"]
        )
        assert result.exit_code == 1
        assert "duplicate configuration" in result.output

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
        result = runner.invoke(
            app,
            [
                "compare",
                "--baseline",
                str(tmp_path / "nope.json"),
                "--candidate",
                str(tmp_path / "also_nope.json"),
            ],
        )
        assert result.exit_code == 1

    def test_compare_valid_files(self, tmp_path: Path):
        from typer.testing import CliRunner

        from chimeraforge.cli import app

        base = tmp_path / "base.json"
        cand = tmp_path / "cand.json"
        _write_bench_json(base, [_make_result(throughput_mean=40.0)])
        _write_bench_json(cand, [_make_result(throughput_mean=50.0)])

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "compare",
                "--baseline",
                str(base),
                "--candidate",
                str(cand),
            ],
        )
        assert result.exit_code == 0

    @pytest.mark.parametrize("unavailable", ["mixed", "negative", "missing"])
    def test_json_compares_each_candidate_and_only_measured_ttft(self, tmp_path, unavailable):
        from typer.testing import CliRunner

        from chimeraforge.cli import app

        base, first, second = (tmp_path / f"{name}.json" for name in ("base", "first", "second"))
        _write_bench_json(base, [_make_result(throughput_mean=100.0, ttft_mean=100.0)])
        unusable = _make_result(throughput_mean=140.0, ttft_mean=120.0)
        ttft = unusable["aggregate"]["ttft_ms"]
        if unavailable == "mixed":
            ttft["min"] = -1.0
        elif unavailable == "negative":
            ttft.update(mean=-1.0, min=-1.0)
        else:
            del unusable["aggregate"]["ttft_ms"]
        _write_bench_json(first, [unusable])
        _write_bench_json(second, [_make_result(throughput_mean=70.0, ttft_mean=70.0)])

        result = CliRunner().invoke(
            app, ["compare", "-b", str(base), "-c", f"{first},{second}", "--json"]
        )

        assert result.exit_code == 0, result.output
        rows = json.loads(result.stdout)
        assert isinstance(rows, list)
        assert [row["candidate_throughput"] for row in rows] == [140.0, 70.0]
        assert rows[0]["candidate_ttft"] == -1.0 and rows[0]["delta_ttft_pct"] is None
        assert rows[1]["candidate_ttft"] == 70.0 and rows[1]["delta_ttft_pct"] == pytest.approx(
            -30.0
        )
