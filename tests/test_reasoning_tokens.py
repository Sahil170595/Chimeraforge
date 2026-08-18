"""Tests for hidden reasoning/thinking-token accounting.

A reasoning model (R1, o-series, QwQ) emits thinking tokens the caller never
sees, but the GPU decodes every one and the KV cache holds them for the life of
the request. Planning on visible output alone under-counts decode by the
reasoning ratio, which is routinely several-fold.

The ratio is deliberately NOT inferred from the model: it is a property of the
prompt and the workload, not of the weights, so it stays an explicit scenario
input that defaults to off.
"""

from __future__ import annotations

import pytest

from chimeraforge.planner.service import run_plan

BASE = dict(
    model_size="8b",
    hardware="H100 80GB",
    request_rate=2.0,
    budget=1e9,
    quality_target=0.0,
    avg_tokens=128,
    latency_slo=60000,
)


def _plan(**over):
    kw = dict(BASE)
    kw.update(over)
    return run_plan(**kw)


class TestDefaultIsOff:
    def test_zero_by_default(self):
        c = _plan().candidates[0]
        assert c.reasoning_tokens == 0
        assert c.decode_tokens_per_req == 128

    def test_explicit_zero_matches_default(self):
        assert (
            _plan(reasoning_tokens=0).candidates[0].decode_tokens_per_req
            == _plan().candidates[0].decode_tokens_per_req
        )

    def test_no_reasoning_warning_when_off(self):
        assert not any("reasoning model" in w for w in _plan().candidates[0].warnings)


class TestDecodeAccounting:
    def test_hidden_tokens_are_added_to_decode(self):
        c = _plan(reasoning_tokens=1000).candidates[0]
        assert c.reasoning_tokens == 1000
        assert c.decode_tokens_per_req == 1128

    def test_latency_grows_with_hidden_tokens(self):
        # The whole point: the request is not done when the visible part is.
        base = _plan().candidates[0].p95_latency_ms
        reasoning = _plan(reasoning_tokens=1000).candidates[0].p95_latency_ms
        assert reasoning > base * 2

    def test_required_throughput_scales(self):
        # More decoded tokens per request at the same rate needs more capacity,
        # which shows up as more GPUs, more batching, or both.
        a = _plan().candidates[0]
        b = _plan(reasoning_tokens=4000).candidates[0]
        assert (b.gpus_total, b.effective_batch) >= (a.gpus_total, a.effective_batch)

    def test_warning_states_the_split_and_its_provenance(self):
        w = [
            x for x in _plan(reasoning_tokens=1000).candidates[0].warnings if "reasoning model" in x
        ]
        assert w and "128 visible" in w[0] and "1000 hidden" in w[0]
        # It must not be presented as a measured property of the model.
        assert "scenario input" in w[0]


class TestPeakSequenceGuard:
    def test_warns_when_peak_exceeds_context(self):
        # prompt 512 + (128 + 8000) blows past a 2048-token window: the plan would
        # otherwise size KV for a window the request cannot finish inside.
        c = _plan(reasoning_tokens=8000, context_length=2048, prompt_tokens=512).candidates[0]
        assert any("peak sequence" in w for w in c.warnings)

    def test_no_peak_warning_when_it_fits(self):
        c = _plan(reasoning_tokens=1000, context_length=8192, prompt_tokens=512).candidates[0]
        assert not any("peak sequence" in w for w in c.warnings)


class TestValidationAndSurfaces:
    def test_cli_rejects_negative(self):
        from typer.testing import CliRunner

        from chimeraforge.cli import app

        r = CliRunner().invoke(app, ["plan", "--model-size", "3b", "--reasoning-tokens", "-5"])
        assert r.exit_code == 1
        assert "reasoning-tokens" in r.output

    def test_cli_accepts_and_reports(self):
        from typer.testing import CliRunner

        from chimeraforge.cli import app

        r = CliRunner().invoke(
            app,
            # Budget/SLO raised deliberately: 512 hidden tokens per request needs
            # ~12 replicas, which the $100/mo default correctly rejects.
            [
                "plan",
                "--model-size",
                "3b",
                "--reasoning-tokens",
                "512",
                "--json",
                "--budget",
                "5000",
                "--latency-slo",
                "60000",
            ],
        )
        assert r.exit_code == 0
        import json

        data = json.loads(r.output[r.output.index("[") : r.output.rindex("]") + 1])
        assert data[0]["reasoning_tokens"] == 512
        assert data[0]["decode_tokens_per_req"] == 128 + 512

    def test_mcp_tool_accepts_reasoning_tokens(self):
        from chimeraforge.mcp_server import plan_deployment

        r = plan_deployment(
            hardware="H100 80GB",
            model_size="8b",
            budget_usd_month=1e9,
            quality_target=0.0,
            reasoning_tokens=1000,
        )
        assert r["ok"]
        assert any("reasoning model" in w for w in r["recommended"]["warnings"])


def test_negative_is_clamped_not_crashing():
    # Library callers bypass CLI validation; a negative must not shrink decode.
    from chimeraforge.planner.engine import enumerate_candidates
    from chimeraforge.planner.models import load_bundled_models

    c = enumerate_candidates(
        models=load_bundled_models(),
        target_models=["llama3.1-8b"],
        hardware="H100 80GB",
        request_rate=1.0,
        latency_slo=60000,
        quality_target=0.0,
        budget=1e9,
        avg_tokens=128,
        context_length=2048,
        reasoning_tokens=-500,
    )
    assert c[0].decode_tokens_per_req == 128
