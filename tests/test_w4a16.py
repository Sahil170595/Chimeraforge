"""Tests for AWQ / GPTQ (W4A16) support on the serving backends.

These are the 4-bit formats people actually run on vLLM and SGLang, so leaving
them out meant the planner offered FP16 or FP8 and nothing between. The honesty
constraint is quality: the TR corpus measures GGUF k-quants, and a 4-bit GGUF
delta is not evidence about AWQ -- different calibration, different error -- so
W4A16 quality is estimated and flagged unscreened.
"""

from __future__ import annotations

import pytest

from chimeraforge.planner.constants import (
    QUANT_BPW,
    QUANT_LEVELS,
    backend_supports_quant,
    quant_family,
)
from chimeraforge.planner.launch import build_launch_command
from chimeraforge.planner.service import run_plan


@pytest.fixture(scope="module")
def plan():
    return run_plan(
        model_size="8b",
        hardware="H100 80GB",
        request_rate=2.0,
        budget=1e9,
        quality_target=0.0,
        latency_slo=60000,
    )


def _w4(plan):
    return [c for c in plan.candidates if c.quant in ("AWQ", "GPTQ")]


class TestQuantTable:
    @pytest.mark.parametrize("q", ["AWQ", "GPTQ"])
    def test_effective_bpw_includes_group_overhead(self, q):
        # 4-bit weights + per-group scales/zeros at group size 128 is ~4.5 bpw,
        # not 4.0 -- the same arithmetic a 4-bit GGUF k-quant lands on.
        assert QUANT_BPW[q] == 4.5

    @pytest.mark.parametrize("q", ["AWQ", "GPTQ"])
    def test_in_the_search_ladder(self, q):
        assert q in QUANT_LEVELS

    def test_ladder_still_descends(self):
        bpws = [QUANT_BPW[q] for q in QUANT_LEVELS]
        assert bpws == sorted(bpws, reverse=True)

    @pytest.mark.parametrize("q", ["AWQ", "GPTQ"])
    def test_own_format_family(self, q):
        assert quant_family(q) == "w4a16"


class TestBackendGating:
    @pytest.mark.parametrize("backend", ["vllm", "tgi", "sglang"])
    def test_serving_backends_take_w4a16(self, backend):
        assert backend_supports_quant(backend, "AWQ")
        assert backend_supports_quant(backend, "GPTQ")

    def test_ollama_does_not(self):
        # llama.cpp serves GGUF, not AWQ/GPTQ checkpoints.
        assert not backend_supports_quant("ollama", "AWQ")
        assert not backend_supports_quant("ollama", "GPTQ")

    def test_offered_in_a_real_plan(self, plan):
        assert _w4(plan)
        assert {c.backend for c in _w4(plan)} <= {"vllm", "tgi", "sglang"}

    def test_never_offered_on_ollama(self, plan):
        assert not [
            c for c in plan.candidates if c.backend == "ollama" and c.quant in ("AWQ", "GPTQ")
        ]


class TestQualityIsUnscreened:
    """A GGUF 4-bit delta is not evidence about AWQ. Say so rather than reuse it."""

    def test_quality_never_claims_measured(self, plan):
        for c in _w4(plan):
            assert c.provenance["quality"] in ("estimated", "unknown")

    def test_warning_says_unscreened(self, plan):
        w = [x for c in _w4(plan) for x in c.warnings if "UNSCREENED" in x]
        assert w
        assert "GGUF" in w[0] and "different calibration" in w[0]

    def test_gguf_quants_get_no_such_warning(self, plan):
        for c in plan.candidates:
            if quant_family(c.quant) == "gguf":
                assert not any("UNSCREENED" in x for x in c.warnings)

    def test_vram_is_still_exact(self, plan):
        # Only quality is unscreened; the footprint is arithmetic.
        for c in _w4(plan):
            assert c.vram_gb > 0


class TestLaunchFlags:
    @pytest.mark.parametrize(
        "backend,flag",
        [
            ("vllm", "--quantization awq"),
            ("sglang", "--quantization awq"),
            ("tgi", "--quantize awq"),
        ],
    )
    def test_emits_the_real_flag(self, backend, flag):
        from chimeraforge.planner.engine import Candidate

        c = Candidate(
            model="org/m",
            quant="AWQ",
            backend=backend,
            n_agents=1,
            vram_gb=9.0,
            quality=0.8,
            quality_tier="negligible",
            throughput_tps=100.0,
            total_throughput_tps=100.0,
            eta=1.0,
            p95_latency_ms=500.0,
            utilisation=0.5,
            monthly_cost=25.0,
            cost_per_1m_tok=0.1,
            safety_refusal=None,
            rtsi_risk="UNKNOWN",
            warnings=[],
        )
        assert flag in build_launch_command(c, None, context_length=4096).command

    def test_no_gguf_note_for_a_real_format(self, plan):
        # AWQ is natively servable, so the "serve a native-equivalent checkpoint"
        # note must not fire.
        lc = build_launch_command(_w4(plan)[0], None, context_length=4096)
        assert not any("GGUF" in n for n in lc.notes)
