"""Tests for duty-cycle-aware effective cost and GPU price scaling.

`cost_per_1m_tok` divides the bill by what a *saturated* fleet could serve. Two
things make that optimistic against a real invoice:

- the planner sizes capacity at or above demand, so you pay for headroom;
- a rented GPU bills for wall-clock, so a fleet sized for a peak it sees part of
  the day still costs the whole month.

`cost_per_1m_tok_effective` divides the same bill by the tokens the workload
actually asks for, which is the number a budget is built from. The arithmetic is
pinned to hand-computed values so these are falsifiable.
"""

from __future__ import annotations

import pytest

from chimeraforge.planner.constants import SECONDS_PER_MONTH
from chimeraforge.planner.service import run_plan

BASE = dict(
    model_size="8b",
    hardware="H100 80GB",
    request_rate=2.0,
    budget=1e9,
    quality_target=0.0,
    latency_slo=60000,
    avg_tokens=128,
)


def _plan(**over):
    kw = dict(BASE)
    kw.update(over)
    return run_plan(**kw).candidates[0]


class TestDefaults:
    def test_duty_cycle_defaults_to_full(self):
        c = _plan()
        assert c.duty_cycle == 1.0
        assert c.gpu_price_multiplier == 1.0

    def test_no_warning_at_defaults(self):
        w = _plan().warnings
        assert not any("duty cycle" in x or "price scaled" in x for x in w)

    def test_at_capacity_figure_is_unchanged_by_defaults(self):
        # The pre-0.20.0 number must survive untouched.
        assert _plan().cost_per_1m_tok > 0


class TestEffectiveCostArithmetic:
    def test_tokens_served_is_rate_times_decode_times_month(self):
        c = _plan()
        assert c.tokens_served_month == pytest.approx(2.0 * 128 * SECONDS_PER_MONTH)

    def test_effective_cost_is_bill_over_tokens_served(self):
        c = _plan()
        expected = c.monthly_cost / c.tokens_served_month * 1e6
        assert c.cost_per_1m_tok_effective == pytest.approx(expected, rel=1e-3)

    def test_duty_cycle_scales_tokens_served(self):
        assert _plan(duty_cycle=0.25).tokens_served_month == pytest.approx(
            _plan().tokens_served_month * 0.25
        )

    def test_halving_duty_doubles_effective_cost(self):
        assert _plan(duty_cycle=0.5).cost_per_1m_tok_effective == pytest.approx(
            _plan().cost_per_1m_tok_effective * 2, rel=1e-3
        )

    def test_duty_cycle_does_not_change_the_bill(self):
        # You rent the GPU either way -- that is the whole point.
        assert _plan(duty_cycle=0.3).monthly_cost == pytest.approx(_plan().monthly_cost)

    def test_effective_is_never_cheaper_than_at_capacity(self):
        # Capacity is sized at or above demand, so the honest figure can only be worse.
        for duty in (1.0, 0.5, 0.1):
            c = _plan(duty_cycle=duty)
            assert c.cost_per_1m_tok_effective >= c.cost_per_1m_tok

    def test_reasoning_tokens_count_toward_tokens_served(self):
        c = _plan(reasoning_tokens=128)
        assert c.tokens_served_month == pytest.approx(2.0 * 256 * SECONDS_PER_MONTH)


class TestPriceMultiplier:
    def test_multiplier_scales_the_bill(self):
        assert _plan(gpu_price_multiplier=0.3).monthly_cost == pytest.approx(
            _plan().monthly_cost * 0.3, rel=1e-3
        )

    def test_multiplier_scales_both_cost_figures(self):
        base, spot = _plan(), _plan(gpu_price_multiplier=0.3)
        assert spot.cost_per_1m_tok == pytest.approx(base.cost_per_1m_tok * 0.3, rel=1e-3)
        assert spot.cost_per_1m_tok_effective == pytest.approx(
            base.cost_per_1m_tok_effective * 0.3, rel=1e-3
        )

    def test_multiplier_does_not_move_performance(self):
        # Price is not physics: throughput, latency and VRAM must be untouched.
        base, spot = _plan(), _plan(gpu_price_multiplier=0.3)
        assert spot.total_throughput_tps == pytest.approx(base.total_throughput_tps)
        assert spot.p95_latency_ms == pytest.approx(base.p95_latency_ms)
        assert spot.vram_gb == pytest.approx(base.vram_gb)

    def test_spot_warning_mentions_reclaim_risk(self):
        w = [x for x in _plan(gpu_price_multiplier=0.3).warnings if "price scaled" in x]
        assert w and "reclaimed" in w[0]

    def test_cheaper_gpus_pass_a_budget_the_on_demand_price_fails(self):
        # The practical consequence: spot pricing changes what fits under a budget.
        tight = dict(BASE, budget=1000.0)
        assert not run_plan(**tight).candidates
        assert run_plan(**dict(tight, gpu_price_multiplier=0.3)).candidates


class TestWarnings:
    def test_duty_warning_quotes_both_figures(self):
        c = _plan(duty_cycle=0.3)
        w = [x for x in c.warnings if "duty cycle" in x]
        assert w and "full capacity" in w[0]

    def test_no_duty_warning_at_full(self):
        assert not any("duty cycle" in x for x in _plan(duty_cycle=1.0).warnings)


class TestClamping:
    def test_duty_above_one_is_clamped(self):
        assert _plan(duty_cycle=5.0).duty_cycle == 1.0

    def test_zero_duty_falls_back_to_full_rather_than_dividing_by_zero(self):
        c = _plan(duty_cycle=0.0)
        assert c.duty_cycle == 1.0
        assert c.cost_per_1m_tok_effective < float("inf")

    def test_negative_multiplier_is_clamped_non_negative(self):
        assert _plan(gpu_price_multiplier=-2.0).gpu_price_multiplier >= 0.0


class TestSurfaces:
    def _run(self, *args):
        from typer.testing import CliRunner

        from chimeraforge.cli import app

        return CliRunner().invoke(app, ["plan", *args])

    def test_cli_rejects_zero_duty(self):
        r = self._run("--model-size", "3b", "--duty-cycle", "0")
        assert r.exit_code == 1 and "duty-cycle" in r.output

    def test_cli_rejects_duty_above_one(self):
        assert self._run("--model-size", "3b", "--duty-cycle", "1.5").exit_code == 1

    def test_cli_rejects_non_positive_multiplier(self):
        r = self._run("--model-size", "3b", "--gpu-price-multiplier", "0")
        assert r.exit_code == 1 and "gpu-price-multiplier" in r.output

    def test_json_carries_the_new_fields(self):
        import json

        r = self._run(
            "--model-size",
            "3b",
            "--json",
            "--budget",
            "5000",
            "--latency-slo",
            "60000",
            "--duty-cycle",
            "0.5",
        )
        assert r.exit_code == 0
        d = json.loads(r.output[r.output.index("[") : r.output.rindex("]") + 1])[0]
        assert d["duty_cycle"] == 0.5
        assert d["cost_per_1m_tok_effective"] > d["cost_per_1m_tok"]

    def test_mcp_tool_accepts_duty_cycle(self):
        from chimeraforge.mcp_server import plan_deployment

        r = plan_deployment(
            hardware="H100 80GB",
            model_size="8b",
            budget_usd_month=1e9,
            quality_target=0.0,
            duty_cycle=0.3,
        )
        assert r["ok"]
        assert any("duty cycle" in w for w in r["recommended"]["warnings"])

    def test_api_comparison_scales_with_duty_cycle(self):
        # An idle API costs nothing while idle GPUs still bill, so a low duty cycle
        # must move the comparison toward the API.
        import json

        def api_monthly(duty):
            r = self._run(
                "--model-size",
                "8b",
                "--hardware",
                "H100 80GB",
                "--json",
                "--compare-api",
                "--budget",
                "1e9",
                "--latency-slo",
                "60000",
                "--quality-target",
                "0",
                "--duty-cycle",
                str(duty),
            )
            d = json.loads(r.output[r.output.index("{") : r.output.rindex("}") + 1])
            return d["api_comparison"]["options"][0]["monthly_cost_usd"]

        assert api_monthly(0.25) == pytest.approx(api_monthly(1.0) * 0.25, rel=0.01)
