"""Tests for separate TTFT and TPOT service-level objectives.

One blended p95 hides which half of the experience a config fails, and the two
failures need opposite fixes: a TTFT miss is prefill-bound (more replicas, shorter
prompt, prefix cache), a TPOT miss is usually a batch that is too large. The gate
therefore checks them separately and names which one bound.

The honesty constraint: the planner predicts a point estimate, not a latency
distribution, so this gates a predicted value and must never be presented as an
attainment percentage.
"""

from __future__ import annotations

import pytest

from chimeraforge.planner.engine import enumerate_candidates
from chimeraforge.planner.models import load_bundled_models
from chimeraforge.planner.service import run_plan

BASE = dict(
    model_size="8b",
    hardware="H100 80GB",
    request_rate=2.0,
    budget=1e9,
    quality_target=0.0,
    latency_slo=60000,
    prompt_tokens=4096,
)


def _plan(**over):
    kw = dict(BASE)
    kw.update(over)
    return run_plan(**kw)


class TestDefaultsAreOff:
    def test_no_slos_by_default(self):
        c = _plan().candidates[0]
        assert c.ttft_slo_ms == 0.0 and c.tpot_slo_ms == 0.0

    def test_results_unchanged_when_off(self):
        # Every pre-0.23.0 number must survive: the dials are additive.
        a, b = _plan().candidates[0], _plan(ttft_slo=None, tpot_slo=None).candidates[0]
        assert (a.backend, a.quant, a.p95_latency_ms) == (b.backend, b.quant, b.p95_latency_ms)

    def test_no_warning_when_off(self):
        assert not any("TTFT/TPOT SLOs" in w for w in _plan().candidates[0].warnings)


class TestGating:
    def test_impossible_ttft_rejects_everything(self):
        # A 4096-token prompt costs ~166ms of prefill on this GPU; 100ms cannot be met.
        assert not _plan(ttft_slo=100.0).candidates

    def test_generous_ttft_admits(self):
        assert _plan(ttft_slo=5000.0).candidates

    def test_surviving_candidates_actually_satisfy_the_slos(self):
        for c in _plan(ttft_slo=5000.0, tpot_slo=200.0).candidates:
            assert c.ttft_ms <= 5000.0
            assert c.tpot_ms <= 200.0

    def test_impossible_tpot_rejects_everything(self):
        assert not _plan(tpot_slo=0.001).candidates

    def test_slos_are_recorded_on_the_candidate(self):
        c = _plan(ttft_slo=5000.0, tpot_slo=200.0).candidates[0]
        assert c.ttft_slo_ms == 5000.0 and c.tpot_slo_ms == 200.0

    def test_tightening_never_adds_candidates(self):
        loose = len(_plan(ttft_slo=5000.0).candidates)
        tight = len(_plan(ttft_slo=200.0).candidates)
        assert tight <= loose


class TestRejectionIsActionable:
    def _trace(self, **over):
        kw = dict(
            models=load_bundled_models(),
            target_models=["llama3.1-8b"],
            hardware="H100 80GB",
            request_rate=2.0,
            latency_slo=60000,
            quality_target=0.0,
            budget=1e9,
            avg_tokens=128,
            context_length=8192,
            prompt_tokens=4096,
        )
        kw.update(over)
        trace: list = []
        enumerate_candidates(trace=trace, **kw)
        return [d for _, _, gate, d in trace if gate == "latency"]

    def test_ttft_failure_says_prefill_bound(self):
        reasons = self._trace(ttft_slo=100.0)
        assert reasons and any("TTFT" in r and "prefill-bound" in r for r in reasons)

    def test_ttft_failure_does_not_blame_batching(self):
        # The fix for a TTFT miss is not a bigger batch, and the message says so.
        assert any("bigger batch will not help" in r for r in self._trace(ttft_slo=100.0))

    def test_tpot_failure_names_tpot(self):
        assert any("TPOT" in r for r in self._trace(tpot_slo=0.001))

    def test_plain_p95_message_when_no_slos_set(self):
        reasons = self._trace(latency_slo=1.0)
        assert reasons and all("TTFT" not in r and "TPOT" not in r for r in reasons)


class TestHonestyAboutWhatIsGated:
    def test_warns_this_is_a_point_estimate_not_attainment(self):
        w = [x for x in _plan(ttft_slo=5000.0).candidates[0].warnings if "TTFT/TPOT SLOs" in x]
        assert w, "setting an SLO must say what is actually being checked"
        assert "not an attainment percentage" in w[0]
        assert "distribution" in w[0]


class TestSurfaces:
    def _run(self, *args):
        from typer.testing import CliRunner

        from chimeraforge.cli import app

        return CliRunner().invoke(app, ["plan", *args])

    def test_cli_rejects_non_positive_ttft(self):
        r = self._run("--model-size", "3b", "--ttft-slo", "0")
        assert r.exit_code == 1 and "ttft-slo" in r.output

    def test_cli_rejects_non_positive_tpot(self):
        r = self._run("--model-size", "3b", "--tpot-slo", "-5")
        assert r.exit_code == 1 and "tpot-slo" in r.output

    def test_json_carries_the_slos(self):
        import json

        r = self._run(
            "--model-size",
            "3b",
            "--json",
            "--budget",
            "5000",
            "--latency-slo",
            "60000",
            "--ttft-slo",
            "9000",
            "--tpot-slo",
            "900",
        )
        assert r.exit_code == 0
        d = json.loads(r.output[r.output.index("[") : r.output.rindex("]") + 1])[0]
        assert d["ttft_slo_ms"] == 9000.0 and d["tpot_slo_ms"] == 900.0

    def test_mcp_tool_accepts_both(self):
        from chimeraforge.mcp_server import plan_deployment

        r = plan_deployment(
            hardware="H100 80GB",
            model_size="8b",
            budget_usd_month=1e9,
            quality_target=0.0,
            latency_slo_ms=60000,
            ttft_slo_ms=5000.0,
            tpot_slo_ms=500.0,
        )
        assert r["ok"] and r["recommended"]
