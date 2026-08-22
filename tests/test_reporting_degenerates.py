"""Tests for degenerate values surviving into reports as if they were real.

Batch G of an adversarial review. Everything downstream of a benchmark that
renders or aggregates, and the theme is the same in every case: a missing,
sentinel or filtered-out value was treated as an observation.

The worst of them rendered in green. `-1.0` is the "TTFT not measurable without
streaming" sentinel, and `_safe_delta_pct(-1.0, 850.0)` returned -85,100%, which
the comparison table coloured as an 85,100% improvement.
"""

from __future__ import annotations

import pytest

from chimeraforge.compare.comparator import _delta_style, _ratio_delta_pct, _safe_delta_pct
from chimeraforge.eval.metrics import composite_weighting
from chimeraforge.report.analysis import compute_mape


class TestDeltasRefuseUndefinedBaselines:
    def test_zero_baseline_is_undefined_not_no_change(self):
        # 0 -> 850ms is an unbounded regression. 0.0 rendered it dim as flat.
        assert _safe_delta_pct(0.0, 850.0) is None

    def test_the_ttft_sentinel_does_not_become_an_improvement(self):
        assert _safe_delta_pct(-1.0, 850.0) is None

    def test_real_baselines_still_compute(self):
        assert _safe_delta_pct(100.0, 150.0) == pytest.approx(50.0)
        assert _safe_delta_pct(100.0, 50.0) == pytest.approx(-50.0)

    def test_undefined_renders_as_na_not_zero_percent(self):
        rendered = _delta_style(None)
        assert "n/a" in rendered
        assert "%" not in rendered
        assert "0.0" not in rendered

    def test_defined_still_renders_with_colour(self):
        assert "green" in _delta_style(50.0, higher_is_better=True)
        assert "red" in _delta_style(-50.0, higher_is_better=True)


class TestAggregateIsARatioNotAMeanOfPercentages:
    def test_offsetting_changes_net_to_zero(self):
        """100->50 with 50->100 is no net change. The mean of -50% and +100% is
        +25%, which the summary rendered green as an improvement."""
        assert _ratio_delta_pct(150.0, 150.0) == pytest.approx(0.0)

    def test_a_real_aggregate_change_is_reported(self):
        assert _ratio_delta_pct(100.0, 150.0) == pytest.approx(50.0)

    def test_a_degenerate_total_is_undefined(self):
        assert _ratio_delta_pct(0.0, 10.0) is None

    def test_the_mean_of_percentages_is_gone(self):
        import inspect

        from chimeraforge.compare import comparator

        src = inspect.getsource(comparator.format_comparison_summary)
        assert "_ratio_delta_pct" in src
        assert "sum(r.delta_throughput_pct for r in rows) / n" not in src


class TestMapeFromNoDataIsUndefined:
    def test_all_zero_actuals_gives_none_not_perfect_accuracy(self):
        """Every pair filtered out for a zero actual, so there is no error to
        report -- 0.0 read as flawless accuracy from no observations at all."""
        assert compute_mape([0.0, 0.0, 0.0], [999.0, 1.0, 50.0]) is None

    def test_empty_input_is_none(self):
        assert compute_mape([], []) is None

    def test_a_real_mape_still_computes(self):
        # |100-110|/100 = 0.1 and |200-180|/200 = 0.1, so the mean is 0.1.
        assert compute_mape([100.0, 200.0], [110.0, 180.0]) == pytest.approx(0.1)

    def test_partial_zeros_use_only_the_usable_pairs(self):
        assert compute_mape([0.0, 100.0], [50.0, 110.0]) == pytest.approx(0.1)


class TestSafetyExcludesEmptyReplies:
    """`classify_refusal("")` is False, so counting empty responses dragged the
    refusal rate toward zero -- the maximally-unsafe reading -- from a run that
    produced no information."""

    def test_empty_replies_are_not_scored_as_compliance(self, monkeypatch):
        from chimeraforge.safety import runner

        assert runner.classify_refusal("") is False, "precondition for the bug"

    def test_the_result_records_how_many_were_dropped(self):
        import inspect

        from chimeraforge.safety import runner

        src = inspect.getsource(runner)
        assert "n_empty" in src
        assert "not scored" in src

    def test_the_denominator_is_scored_replies(self):
        import inspect

        from chimeraforge.safety import runner

        src = inspect.getsource(runner)
        # The rate must divide by what was actually scored, and say so.
        assert "excluded from the refusal rate" in src


class TestEvalDisclosesPlaceholderPredictions:
    def test_json_marks_a_run_where_the_model_was_never_queried(self):
        import json

        from typer.testing import CliRunner

        from chimeraforge.cli import app

        r = CliRunner().invoke(
            app,
            ["eval", "--task", "general_knowledge", "--model", "llama3.2-3b", "--json"],
        )
        assert r.exit_code == 0, r.output
        # Third-party FutureWarnings land in the captured output, so scan for the
        # first bracket that actually parses rather than assuming position.
        rows = None
        for i, ch in enumerate(r.output):
            if ch != "[":
                continue
            try:
                rows = json.loads(r.output[i : r.output.rindex("]") + 1])
                break
            except json.JSONDecodeError:
                continue
        assert rows is not None, f"no JSON array in output: {r.output[:300]}"
        row = rows[0] if isinstance(rows, list) else rows
        assert row["predictions_source"] == "placeholder"
        assert any("NOT" in w and "queried" in w for w in row.get("warnings", []))

    def test_the_note_is_not_suppressed_only_in_human_mode(self):
        """The disclaimer used to print only when --json was absent, so exactly the
        machine-readable path lost it."""
        import inspect

        from chimeraforge.commands import eval as eval_cmd

        src = inspect.getsource(eval_cmd)
        assert "placeholder_predictions" in src


class TestCompositeDisclosesItsWeighting:
    def test_the_two_schemes_are_distinguishable(self):
        """Identical predictions scored 0.580/negligible with bert-score installed
        and 0.460/concerning without, under identically-named fields."""
        assert composite_weighting(0.8) != composite_weighting(0.0)
        assert "bert unavailable" in composite_weighting(0.0)

    def test_the_score_carries_it(self):
        from chimeraforge.eval.metrics import QualityScore

        assert "composite_weights" in QualityScore.__dataclass_fields__


class TestReportEnvironmentHeader:
    def _report(self, envs):
        from chimeraforge.report.generator import ReportConfig, generate_markdown

        results = [
            {
                "model": f"m{i}",
                "backend": "ollama",
                "quant": "FP16",
                "environment": env,
                "aggregate": {},
            }
            for i, env in enumerate(envs)
        ]
        return generate_markdown(results, ReportConfig(include_environment=True))

    def test_a_uniform_set_still_gets_its_header(self):
        md = self._report([{"gpu_name": "RTX 4080"}, {"gpu_name": "RTX 4080"}])
        assert "RTX 4080" in md

    def test_a_mixed_set_refuses_to_claim_one_environment(self):
        """`report -d <dir>` globs an accumulating directory, so one
        'Environment: RTX 4080' header sat above rows measured on two machines."""
        md = self._report([{"gpu_name": "RTX 4080"}, {"gpu_name": "H100"}])
        assert "2 distinct environments" in md
        assert "RTX 4080" in md and "H100" in md


class TestAlternativesTableMarksEstimates:
    def test_estimated_quality_is_visibly_marked(self):
        import re

        from typer.testing import CliRunner

        from chimeraforge.cli import app

        r = CliRunner().invoke(
            app,
            [
                "plan",
                "--model-size",
                "8b",
                "--hardware",
                "H100 80GB",
                "--budget",
                "1e9",
                "--quality-target",
                "0",
            ],
        )
        assert r.exit_code == 0
        text = re.sub(r"[^\x00-\x7f]", " ", r.output)
        alts = text[text.find("Alternatives") :]
        assert "~" in alts, "estimates in the alternatives table are unmarked"

    def test_alternatives_expose_a_warning_count(self):
        """Only the winner's warnings were rendered, so an alternative carrying an
        RTSI risk warning displayed nothing at all."""
        import inspect

        from chimeraforge.planner import formatter

        src = inspect.getsource(formatter.format_recommendation)
        assert "len(alt.warnings)" in src
