"""Tests for prefix-cache-aware prefill / TTFT.

vLLM, TGI and SGLang skip prefill for a prompt span already resident in cache.
Chatbot and agent traffic -- the workload presets this planner already ships --
reuse a long system prompt and conversation head on nearly every turn, so prefill
stops being the dominant TTFT term. Charging the full prompt every time overstates
TTFT and the end-to-end tail with it.

Two properties are guarded alongside the arithmetic:

- the hit rate **defaults to 0 and is never inferred** -- it is a property of the
  traffic, not of the model, so there is nothing in a spec to read it from;
- the KV memory a shared prefix saves is deliberately **not** deducted, because
  under-sizing KV is the direction that claims a fit that is not there.
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
    prompt_tokens=4096,
    latency_slo=60000,
)


def _plan(**over):
    kw = dict(BASE)
    kw.update(over)
    return run_plan(**kw).candidates[0]


class TestDefaultIsOff:
    def test_zero_by_default(self):
        c = _plan()
        assert c.prefix_cache_hit_rate == 0.0
        assert c.prefill_tokens_effective == 4096

    def test_no_warning_when_off(self):
        assert not any("prefix cache" in w for w in _plan().warnings)

    def test_explicit_zero_matches_default(self):
        assert _plan(prefix_cache_hit_rate=0.0).ttft_ms == _plan().ttft_ms


class TestPrefillArithmetic:
    @pytest.mark.parametrize("rate,expected", [(0.0, 4096), (0.25, 3072), (0.5, 2048), (0.9, 410)])
    def test_uncached_remainder_is_prefilled(self, rate, expected):
        assert _plan(prefix_cache_hit_rate=rate).prefill_tokens_effective == expected

    def test_full_hit_still_prefills_one_token(self):
        # A fully cached prompt still runs the newest token through the stack, so
        # TTFT never truly reaches zero.
        assert _plan(prefix_cache_hit_rate=1.0).prefill_tokens_effective == 1

    def test_ttft_scales_with_the_uncached_fraction(self):
        # Prefill is compute-bound and linear in tokens, so halving the tokens
        # halves TTFT.
        full = _plan().ttft_ms
        half = _plan(prefix_cache_hit_rate=0.5).ttft_ms
        assert half == pytest.approx(full / 2, rel=0.02)

    def test_ttft_is_monotonically_non_increasing(self):
        ttfts = [_plan(prefix_cache_hit_rate=r).ttft_ms for r in (0.0, 0.25, 0.5, 0.75, 1.0)]
        assert ttfts == sorted(ttfts, reverse=True)

    def test_tail_latency_improves_too(self):
        # TTFT feeds the end-to-end p95, so the benefit must reach the tail.
        assert _plan(prefix_cache_hit_rate=0.9).p95_latency_ms < _plan().p95_latency_ms


class TestKvIsNotDiscounted:
    """A shared prefix does save KV in a real server; we do not model that."""

    def test_vram_unchanged_by_hit_rate(self):
        assert _plan(prefix_cache_hit_rate=0.9).vram_gb == pytest.approx(_plan().vram_gb)

    def test_concurrency_ceiling_unchanged(self):
        assert _plan(prefix_cache_hit_rate=0.9).max_concurrent_seqs == _plan().max_concurrent_seqs

    def test_warning_says_kv_is_not_deducted(self):
        w = [x for x in _plan(prefix_cache_hit_rate=0.9).warnings if "prefix cache" in x]
        assert w and "NOT deducted" in w[0]

    def test_warning_names_it_a_scenario_input(self):
        w = [x for x in _plan(prefix_cache_hit_rate=0.5).warnings if "prefix cache" in x]
        assert w and "scenario input" in w[0]


class TestClamping:
    def test_negative_is_clamped_to_zero(self):
        # Library callers bypass CLI validation; a negative must not inflate prefill.
        assert _plan(prefix_cache_hit_rate=-0.5).prefill_tokens_effective == 4096

    def test_above_one_is_clamped(self):
        assert _plan(prefix_cache_hit_rate=5.0).prefill_tokens_effective == 1


class TestSurfaces:
    def _run(self, *args):
        from typer.testing import CliRunner

        from chimeraforge.cli import app

        return CliRunner().invoke(app, ["plan", *args])

    def test_cli_rejects_out_of_range(self):
        r = self._run("--model-size", "3b", "--prefix-cache-hit-rate", "1.5")
        assert r.exit_code == 1
        assert "prefix-cache-hit-rate" in r.output

    def test_cli_rejects_negative(self):
        assert self._run("--model-size", "3b", "--prefix-cache-hit-rate", "-0.2").exit_code == 1

    def test_cli_reports_both_fields(self):
        import json

        r = self._run(
            "--model-size",
            "3b",
            "--prefix-cache-hit-rate",
            "0.5",
            "--json",
            "--budget",
            "5000",
            "--latency-slo",
            "60000",
            "--prompt-tokens",
            "1000",
        )
        assert r.exit_code == 0
        data = json.loads(r.output[r.output.index("[") : r.output.rindex("]") + 1])
        assert data[0]["prefix_cache_hit_rate"] == 0.5
        assert data[0]["prefill_tokens_effective"] == 500

    def test_mcp_tool_accepts_hit_rate(self):
        from chimeraforge.mcp_server import plan_deployment

        r = plan_deployment(
            hardware="H100 80GB",
            model_size="8b",
            budget_usd_month=1e9,
            quality_target=0.0,
            prefix_cache_hit_rate=0.9,
        )
        assert r["ok"]
        assert any("prefix cache" in w for w in r["recommended"]["warnings"])

    def test_composes_with_reasoning_tokens(self):
        # Prefill shrinks, decode grows -- the two dials must not interfere.
        c = _plan(prefix_cache_hit_rate=0.9, reasoning_tokens=1000)
        assert c.prefill_tokens_effective == 410
        assert c.decode_tokens_per_req == 1128
