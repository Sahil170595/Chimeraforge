"""Tests for the 7 predictive planner models and their edge cases."""

from __future__ import annotations

import pytest

from chimeraforge.planner.constants import QUANT_LEVELS, MODEL_PARAMS_B
from chimeraforge.planner.models import (
    CostModel,
    LatencyModel,
    QualityModel,
    SafetyModel,
    ScalingModel,
    ThroughputModel,
    VRAMModel,
)


# -- VRAM Model -------------------------------------------------------


class TestVRAMModel:
    def test_quant_reduces_vram(self, bundled_models):
        fp16 = bundled_models.vram.predict("llama3.2-3b", "FP16", 2048)
        q4 = bundled_models.vram.predict("llama3.2-3b", "Q4_K_M", 2048)
        assert q4 < fp16

    def test_larger_model_more_vram(self, bundled_models):
        small = bundled_models.vram.predict("llama3.2-1b", "FP16", 2048)
        large = bundled_models.vram.predict("llama3.1-8b", "FP16", 2048)
        assert large > small

    def test_longer_context_more_vram(self, bundled_models):
        short = bundled_models.vram.predict("llama3.2-3b", "FP16", 512)
        long = bundled_models.vram.predict("llama3.2-3b", "FP16", 8192)
        assert long > short

    def test_unknown_model_uses_defaults(self):
        m = VRAMModel(overhead_factor=1.1)
        vram = m.predict("unknown-model", "FP16", 2048)
        assert vram > 0

    def test_vram_positive(self, bundled_models):
        for model in MODEL_PARAMS_B:
            for quant in QUANT_LEVELS:
                v = bundled_models.vram.predict(model, quant, 2048)
                assert v > 0, f"VRAM should be positive for {model} {quant}"


# -- KV-cache-bound concurrency (0.6.0) -------------------------------


class TestMaxConcurrentSeqs:
    ARCH = {"n_layers": 28, "n_kv_heads": 8, "d_head": 128}  # llama3.2-3b

    def test_kv_cache_scales_with_context_batch_and_heads(self):
        base = VRAMModel.kv_cache_gb(self.ARCH, 2048, 1)
        assert VRAMModel.kv_cache_gb(self.ARCH, 4096, 1) == pytest.approx(2 * base)
        assert VRAMModel.kv_cache_gb(self.ARCH, 2048, 4) == pytest.approx(4 * base)
        wide = {**self.ARCH, "n_kv_heads": 16}
        assert VRAMModel.kv_cache_gb(wide, 2048, 1) == pytest.approx(2 * base)

    def test_bigger_gpu_holds_more_seqs(self):
        m = VRAMModel()
        small = m.max_concurrent_seqs(3.21, "Q4_K_M", self.ARCH, 2048, 12.0)
        big = m.max_concurrent_seqs(3.21, "Q4_K_M", self.ARCH, 2048, 24.0)
        assert big > small > 0

    def test_longer_context_fewer_seqs(self):
        m = VRAMModel()
        short = m.max_concurrent_seqs(3.21, "Q4_K_M", self.ARCH, 1024, 24.0)
        long = m.max_concurrent_seqs(3.21, "Q4_K_M", self.ARCH, 8192, 24.0)
        assert short > long

    def test_weights_dont_fit_returns_zero(self):
        m = VRAMModel()
        # 70B FP16 (~154 GB) cannot fit a 24 GB card.
        assert m.max_concurrent_seqs(70.0, "FP16", self.ARCH, 2048, 24.0) == 0

    def test_quantization_increases_capacity(self):
        m = VRAMModel()
        fp16 = m.max_concurrent_seqs(3.21, "FP16", self.ARCH, 2048, 24.0)
        q4 = m.max_concurrent_seqs(3.21, "Q4_K_M", self.ARCH, 2048, 24.0)
        assert q4 > fp16  # smaller weights leave more VRAM for KV


# -- Throughput Model -------------------------------------------------


class TestThroughputModel:
    def test_exact_lookup(self, bundled_models):
        tps = bundled_models.throughput.predict("llama3.2-3b", "ollama", "FP16")
        assert tps == pytest.approx(95.86, rel=0.01)

    def test_quant_multiplier_fallback(self, bundled_models):
        fp16 = bundled_models.throughput.predict("llama3.2-3b", "ollama", "FP16")
        q4 = bundled_models.throughput.predict("llama3.2-3b", "ollama", "Q4_K_M")
        assert q4 > fp16

    def test_larger_model_slower(self, bundled_models):
        small = bundled_models.throughput.predict("llama3.2-1b", "ollama", "FP16")
        large = bundled_models.throughput.predict("llama3.2-3b", "ollama", "FP16")
        assert small > large

    def test_bandwidth_scaling(self, bundled_models):
        base = bundled_models.throughput.predict("llama3.2-3b", "ollama", "FP16")
        scaled = bundled_models.throughput.predict(
            "llama3.2-3b",
            "ollama",
            "FP16",
            hardware="RTX 4090 24GB",
        )
        assert scaled > base

    def test_minimum_throughput(self, bundled_models):
        tps = bundled_models.throughput.predict("nonexistent-model", "ollama", "FP16")
        assert tps >= 0.1


# -- Scaling Model ----------------------------------------------------


class TestScalingModel:
    def test_eta_n1_is_one(self, bundled_models):
        eta = bundled_models.scaling.predict_eta("llama3.2-3b", "ollama", 1)
        assert eta == pytest.approx(1.0)

    def test_eta_decreases_with_n(self, bundled_models):
        eta2 = bundled_models.scaling.predict_eta("llama3.2-3b", "ollama", 2)
        eta8 = bundled_models.scaling.predict_eta("llama3.2-3b", "ollama", 8)
        assert eta2 > eta8
        assert eta8 > 0

    def test_unknown_model_uses_defaults(self):
        m = ScalingModel()
        eta = m.predict_eta("unknown", "ollama", 4)
        assert 0 < eta < 1


# -- Quality Model ----------------------------------------------------


class TestQualityModel:
    def test_fp16_best_quality(self, bundled_models):
        fp16 = bundled_models.quality.predict("llama3.2-1b", "FP16")
        q2 = bundled_models.quality.predict("llama3.2-1b", "Q2_K")
        assert fp16 >= q2

    def test_quality_in_range(self, bundled_models):
        q = bundled_models.quality.predict("llama3.2-3b", "Q4_K_M")
        assert 0 <= q <= 1

    def test_quality_tier_fp16(self, bundled_models):
        tier = bundled_models.quality.quality_tier("llama3.2-1b", "FP16")
        assert tier == "negligible"

    def test_unknown_model_returns_default(self):
        m = QualityModel()
        q = m.predict("nonexistent", "FP16")
        assert q == 0.5


# -- Safety Model -----------------------------------------------------


class TestSafetyModel:
    def test_refusal_lookup_collapse_cell(self, bundled_models):
        # TR134: llama3.2-1b refusal collapses from ~0.94 (FP16) to ~0.37 (Q2_K).
        fp16 = bundled_models.safety.predict_refusal("llama3.2-1b", "FP16")
        q2k = bundled_models.safety.predict_refusal("llama3.2-1b", "Q2_K")
        assert fp16 > 0.9
        assert q2k == pytest.approx(0.368, abs=0.01)
        assert q2k < fp16

    def test_refusal_safe_cell(self, bundled_models):
        # Q4_K_M holds refusal high - should clear a 0.8 safety bar.
        q4 = bundled_models.safety.predict_refusal("llama3.2-1b", "Q4_K_M")
        assert q4 == pytest.approx(0.905, abs=0.01)
        assert q4 >= 0.8

    def test_unknown_model_returns_none(self, bundled_models):
        # qwen2.5-3b is in the planner registry but has no safety data.
        # Lookup-only: must return None, never a fabricated guess.
        assert bundled_models.safety.predict_refusal("qwen2.5-3b", "Q4_K_M") is None

    def test_non_gguf_quant_returns_none(self, bundled_models):
        # AWQ/GPTQ are excluded from the safety block (planner can't search them).
        assert bundled_models.safety.predict_refusal("llama3.2-1b", "AWQ") is None

    def test_rtsi_risk_high_on_collapse_cells(self, bundled_models):
        assert bundled_models.safety.rtsi_risk("llama3.2-1b", "Q2_K") == "HIGH"
        assert bundled_models.safety.rtsi_risk("qwen2.5-1.5b", "Q2_K") == "HIGH"

    def test_rtsi_risk_unknown_when_unscreened(self, bundled_models):
        assert bundled_models.safety.rtsi_risk("qwen2.5-3b", "Q4_K_M") == "UNKNOWN"

    def test_refusal_drop_pp_negative_on_regression(self, bundled_models):
        drop = bundled_models.safety.refusal_drop_pp("llama3.2-1b", "Q2_K")
        assert drop is not None
        assert drop < -40  # ~-57pp regression

    def test_refusal_drop_pp_none_when_unscreened(self, bundled_models):
        assert bundled_models.safety.refusal_drop_pp("qwen2.5-3b", "Q4_K_M") is None

    def test_fp16_baselines_cover_overlap_models(self, bundled_models):
        baselines = bundled_models.safety.fp16_baselines
        for m in ("llama3.2-1b", "llama3.2-3b", "qwen2.5-1.5b", "phi-2"):
            assert m in baselines
        assert baselines["llama3.2-1b"] > 0.9

    def test_bundled_safety_is_fitted_and_populated(self, bundled_models):
        assert bundled_models.safety.fitted is True
        assert len(bundled_models.safety.lookup) >= 40

    def test_serialization_round_trip(self):
        m = SafetyModel(
            lookup={"llama3.2-1b|Q2_K": 0.37, "llama3.2-1b|FP16": 0.94},
            fp16_baselines={"llama3.2-1b": 0.94},
            rtsi={"llama3.2-1b|Q2_K": {"score": 0.56, "risk": "HIGH"}},
            fitted=True,
        )
        restored = SafetyModel.from_dict(m.to_dict())
        assert restored.predict_refusal("llama3.2-1b", "Q2_K") == 0.37
        assert restored.rtsi_risk("llama3.2-1b", "Q2_K") == "HIGH"
        assert restored.refusal_drop_pp("llama3.2-1b", "Q2_K") == pytest.approx(-57.0)
        assert restored.fitted is True

    def test_empty_model_defaults(self):
        m = SafetyModel()
        assert m.predict_refusal("anything", "Q4_K_M") is None
        assert m.rtsi_risk("anything", "Q4_K_M") == "UNKNOWN"
        assert m.fitted is False


# -- Cost Model -------------------------------------------------------


class TestCostModel:
    def test_cost_per_1m_formula(self):
        m = CostModel(hw_cost_per_hour=0.035)
        cost = m.predict_cost_per_1m(50.0)
        expected = 0.035 / (50.0 * 3600) * 1_000_000
        assert cost == pytest.approx(expected)

    def test_monthly_cost(self):
        m = CostModel(hw_cost_per_hour=0.035)
        assert m.predict_monthly() == pytest.approx(25.2)

    def test_higher_throughput_lower_cost(self):
        m = CostModel()
        assert m.predict_cost_per_1m(100.0) < m.predict_cost_per_1m(10.0)

    def test_zero_throughput_returns_inf(self):
        m = CostModel()
        assert m.predict_cost_per_1m(0.0) == float("inf")

    def test_override_hw_cost(self):
        m = CostModel(hw_cost_per_hour=0.035)
        cost1 = m.predict_cost_per_1m(50.0, hw_cost_hr=1.0)
        cost2 = m.predict_cost_per_1m(50.0, hw_cost_hr=0.035)
        assert cost1 > cost2


# -- Latency Model ----------------------------------------------------


class TestLatencyModel:
    def test_low_load_near_service_time(self, bundled_models):
        result = bundled_models.latency.predict_p95(
            "llama3.2-3b",
            "ollama",
            request_rate=0.001,
            n_agents=1,
        )
        assert result["p95_ms"] == pytest.approx(result["service_ms"], rel=0.1)
        assert result["utilisation"] < 0.1

    def test_high_load_increases_latency(self, bundled_models):
        low = bundled_models.latency.predict_p95(
            "llama3.2-3b",
            "ollama",
            request_rate=0.01,
        )
        high = bundled_models.latency.predict_p95(
            "llama3.2-3b",
            "ollama",
            request_rate=0.4,
        )
        assert high["p95_ms"] > low["p95_ms"]

    def test_saturated_flag(self, bundled_models):
        result = bundled_models.latency.predict_p95(
            "llama3.2-3b",
            "ollama",
            request_rate=10.0,
        )
        assert result["saturated"]


# -- Prefill / TTFT (0.6.0) ---------------------------------------------------


class TestPrefillTTFT:
    def test_ttft_scales_with_params(self):
        m = LatencyModel()
        small = m.predict_ttft_ms(7.0, 512, "RTX 4090 24GB")
        big = m.predict_ttft_ms(14.0, 512, "RTX 4090 24GB")
        assert big == pytest.approx(2 * small, rel=1e-3)  # linear in params

    def test_ttft_scales_with_prompt_length(self):
        m = LatencyModel()
        short = m.predict_ttft_ms(7.0, 512, "RTX 4090 24GB")
        long = m.predict_ttft_ms(7.0, 2048, "RTX 4090 24GB")
        assert long == pytest.approx(4 * short, rel=1e-3)  # linear in prompt tokens

    def test_faster_gpu_lower_ttft(self):
        m = LatencyModel()
        slow = m.predict_ttft_ms(7.0, 512, "T4 16GB")  # 65 TFLOPS
        fast = m.predict_ttft_ms(7.0, 512, "H100 80GB")  # 989 TFLOPS
        assert fast < slow

    def test_unknown_gpu_returns_zero(self):
        # No compute data -> 0.0 so the caller omits prefill rather than guessing.
        assert LatencyModel().predict_ttft_ms(7.0, 512, "Some Unknown GPU") == 0.0

    def test_zero_params_or_prompt_returns_zero(self):
        m = LatencyModel()
        assert m.predict_ttft_ms(0, 512, "RTX 4090 24GB") == 0.0
        assert m.predict_ttft_ms(7.0, 0, "RTX 4090 24GB") == 0.0

    def test_p95_includes_prefill(self, bundled_models):
        # Same config, with vs without a prefill term -> prefill adds to service.
        base = bundled_models.latency.predict_p95(
            "llama3.2-3b", "ollama", request_rate=0.01, n1_tps=100.0, avg_tokens=128
        )
        with_prefill = bundled_models.latency.predict_p95(
            "llama3.2-3b", "ollama", request_rate=0.01, n1_tps=100.0, avg_tokens=128, ttft_ms=200.0
        )
        assert with_prefill["service_ms"] == pytest.approx(base["service_ms"] + 200.0, rel=1e-3)


# -- Scaling Model Edge Cases -------------------------------------------------


class TestScalingEdgeCases:
    def test_n_zero(self, bundled_models):
        eta = bundled_models.scaling.predict_eta("llama3.2-3b", "ollama", 0)
        assert eta == 1.0  # n <= 1 returns 1.0

    def test_n_negative(self, bundled_models):
        eta = bundled_models.scaling.predict_eta("llama3.2-3b", "ollama", -1)
        assert eta == 1.0  # n <= 1 returns 1.0


# -- VRAM Batch Size ----------------------------------------------------------


class TestVRAMBatchSize:
    def test_larger_batch_more_vram(self, bundled_models):
        v1 = bundled_models.vram.predict("llama3.2-3b", "FP16", 2048, batch_size=1)
        v4 = bundled_models.vram.predict("llama3.2-3b", "FP16", 2048, batch_size=4)
        assert v4 > v1


# -- Latency Edge Cases -------------------------------------------------------


class TestLatencyEdgeCases:
    def test_saturated_returns_inf(self, bundled_models):
        result = bundled_models.latency.predict_p95(
            "llama3.2-3b",
            "ollama",
            request_rate=10.0,
        )
        assert result["p95_ms"] == float("inf")
        assert result["saturated"]

    def test_zero_service_time(self):
        """mu fallback should be large, not tiny."""
        m = LatencyModel()
        result = m.predict_p95(
            "test",
            "ollama",
            request_rate=1.0,
            avg_tokens=0,
            throughput_model=ThroughputModel(lookup={"test|ollama|FP16": 100}),
        )
        # With zero avg_tokens, service_ms = 0, mu should be very large
        assert result["total_capacity_rps"] > 100
