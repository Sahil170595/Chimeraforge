"""Tests for FP8 support and backend/quant format gating.

Two claims are locked here:

1. A backend is only offered formats it actually serves. GGUF is llama.cpp's
   (Ollama); vLLM/TGI serve float and FP8 checkpoints. The planner used to offer
   every GGUF level on every backend and price it with a llama.cpp-measured
   speedup -- a config nobody could deploy, costed from a mismatched measurement.
2. FP8 is only offered where FP8 tensor cores exist (Ada / Hopper / Blackwell /
   CDNA3), not on Ampere or Turing.
"""

from __future__ import annotations

import pytest

from chimeraforge.planner.constants import (
    QUANT_BPW,
    QUANT_LEVELS,
    backend_supports_quant,
    quant_family,
)
from chimeraforge.planner.engine import enumerate_candidates
from chimeraforge.planner.hardware import GPU_DB, get_gpu
from chimeraforge.planner.launch import build_launch_command
from chimeraforge.planner.models import load_bundled_models


@pytest.fixture(scope="module")
def models():
    return load_bundled_models()


def _plan(models, hardware, **over):
    kw = dict(
        target_models=["llama3.1-8b"],
        hardware=hardware,
        request_rate=2.0,
        latency_slo=10000,
        quality_target=0.0,
        budget=1e9,
        avg_tokens=128,
        context_length=2048,
    )
    kw.update(over)
    return enumerate_candidates(models=models, **kw)


class TestQuantTable:
    def test_fp8_is_exactly_one_byte_per_param(self):
        assert QUANT_BPW["FP8"] == 8.0

    def test_fp8_in_search_ladder(self):
        assert "FP8" in QUANT_LEVELS

    def test_ladder_still_descends_by_bpw(self):
        bpws = [QUANT_BPW[q] for q in QUANT_LEVELS]
        assert bpws == sorted(bpws, reverse=True)

    def test_fp8_throughput_multiplier_matches_same_width_quant(self, models):
        # No fitted FP8 entry: the nearest-bpw fallback must land on the other
        # 8-bit format rather than silently returning the FP16 rate.
        assert models.throughput.quant_multiplier("FP8") == pytest.approx(
            models.throughput.quant_multiplier("Q8_0")
        )


class TestFormatFamilies:
    @pytest.mark.parametrize(
        "quant,family",
        [
            ("FP16", "float"),
            ("BF16", "float"),
            ("FP8", "fp8"),
            ("Q4_K_M", "gguf"),
            ("IQ4_XS", "gguf"),
        ],
    )
    def test_classification(self, quant, family):
        assert quant_family(quant) == family

    @pytest.mark.parametrize("backend", ["vllm", "tgi"])
    def test_serving_backends_take_float_and_fp8_not_gguf(self, backend):
        assert backend_supports_quant(backend, "FP16")
        assert backend_supports_quant(backend, "FP8")
        assert not backend_supports_quant(backend, "Q4_K_M")

    def test_ollama_takes_gguf_and_float_not_fp8(self):
        assert backend_supports_quant("ollama", "Q4_K_M")
        assert backend_supports_quant("ollama", "FP16")
        assert not backend_supports_quant("ollama", "FP8")

    def test_unknown_backend_is_permissive(self):
        # A custom backend must not have everything silently rejected.
        assert backend_supports_quant("sglang", "Q4_K_M")


class TestHardwareFp8Capability:
    @pytest.mark.parametrize(
        "gpu",
        [
            "H100 80GB",
            "H200 141GB",
            "B200 180GB",
            "RTX 4090 24GB",
            "L4 24GB",
            "RTX 5090 32GB",
            "MI300X 192GB",
        ],
    )
    def test_fp8_capable(self, gpu):
        assert GPU_DB[gpu].fp8_supported

    @pytest.mark.parametrize("gpu", ["A100 40GB", "A100 80GB", "T4 16GB", "RTX 3090 24GB"])
    def test_pre_ada_has_no_fp8(self, gpu):
        assert not GPU_DB[gpu].fp8_supported

    def test_every_gpu_declares_capability(self):
        assert all(isinstance(s.fp8_supported, bool) for s in GPU_DB.values())


class TestEngineGating:
    def test_serving_backends_lose_gguf(self, models):
        got = {(c.backend, c.quant) for c in _plan(models, "H100 80GB")}
        assert not [q for b, q in got if b in ("vllm", "tgi") and quant_family(q) == "gguf"]

    def test_ollama_keeps_gguf(self, models):
        got = {(c.backend, c.quant) for c in _plan(models, "H100 80GB")}
        assert [q for b, q in got if b == "ollama" and quant_family(q) == "gguf"]

    def test_fp8_offered_on_capable_gpu(self, models):
        got = {(c.backend, c.quant) for c in _plan(models, "H100 80GB")}
        assert ("vllm", "FP8") in got

    def test_fp8_absent_on_ampere(self, models):
        got = {(c.backend, c.quant) for c in _plan(models, "A100 80GB")}
        assert not [1 for _, q in got if q == "FP8"]

    def test_ollama_never_offered_fp8(self, models):
        got = {(c.backend, c.quant) for c in _plan(models, "H100 80GB")}
        assert ("ollama", "FP8") not in got

    def test_rejections_explain_themselves(self, models):
        trace: list = []
        _plan(models, "A100 80GB", trace=trace)
        reasons = [d for _, _, gate, d in trace if gate == "format"]
        assert any("does not serve" in r for r in reasons)
        assert any("no FP8 tensor cores" in r for r in reasons)

    def test_fp8_vram_is_half_of_fp16(self, models):
        cands = _plan(models, "H100 80GB")
        fp16 = next(c for c in cands if c.backend == "vllm" and c.quant == "FP16")
        fp8 = next(c for c in cands if c.backend == "vllm" and c.quant == "FP8")
        # Weights halve; KV cache and activations are unchanged, so the total is
        # lower but not exactly half.
        assert fp8.vram_gb < fp16.vram_gb

    def test_fp8_quality_is_estimated_never_measured(self, models):
        fp8 = next(c for c in _plan(models, "H100 80GB") if c.quant == "FP8")
        # FP8 is absent from the TR quality corpus; it must not claim measurement.
        assert fp8.provenance["quality"] in ("estimated", "unknown")


class TestLaunchCommand:
    def test_vllm_emits_fp8_flag(self):
        from chimeraforge.planner.engine import Candidate

        c = Candidate(
            model="org/m",
            quant="FP8",
            backend="vllm",
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
        lc = build_launch_command(c, None, context_length=2048)
        assert "--quantization fp8" in lc.command
        # FP8 is a real vLLM format, so the GGUF "serve a different checkpoint"
        # note must not fire.
        assert not any("GGUF" in n for n in lc.notes)

    def test_tgi_emits_quantize_fp8(self):
        from chimeraforge.planner.engine import Candidate

        c = Candidate(
            model="org/m",
            quant="FP8",
            backend="tgi",
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
        lc = build_launch_command(c, None, context_length=2048)
        assert "--quantize fp8" in lc.command


def test_reference_gpu_unchanged_for_gguf_planning():
    # The RTX 4080 reference path (Ollama + GGUF) must be untouched by the gate.
    m = load_bundled_models()
    got = {(c.backend, c.quant) for c in _plan(m, "RTX 4080 12GB", budget=1e9)}
    assert ("ollama", "Q4_K_M") in got
    assert get_gpu("RTX 4080 12GB").fp8_supported
