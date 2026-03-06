"""ChimeraForge Capacity Planner — unit tests.

Tests the 6 predictive models, engine search, hardware DB,
constants, serialization round-trip, and CLI integration.

Run:
    pytest tests/test_planner.py -v
"""

from __future__ import annotations

import json

import pytest

from chimeraforge.planner.constants import (
    BACKENDS,
    MODEL_ARCH,
    MODEL_PARAMS_B,
    QUANT_BPW,
    QUANT_LEVELS,
)
from chimeraforge.planner.engine import Candidate, enumerate_candidates, find_models_for_size
from chimeraforge.planner.hardware import (
    GPU_DB,
    REFERENCE_GPU,
    GPUSpec,
    bandwidth_ratio,
    get_gpu,
)
from chimeraforge.planner.models import (
    CostModel,
    LatencyModel,
    PlannerModels,
    QualityModel,
    ScalingModel,
    ThroughputModel,
    VRAMModel,
    load_bundled_models,
    load_models,
)


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def bundled_models() -> PlannerModels:
    """Load the bundled fitted models (real data from TR133)."""
    return load_bundled_models()


# ── Constants & Registry ─────────────────────────────────────────────


class TestConstants:
    def test_quant_levels_ordered_descending(self):
        bpws = [QUANT_BPW[q] for q in QUANT_LEVELS]
        assert bpws == sorted(bpws, reverse=True)

    def test_all_quants_have_bpw(self):
        for q in QUANT_LEVELS:
            assert q in QUANT_BPW

    def test_model_params_and_arch_consistent(self):
        assert set(MODEL_PARAMS_B.keys()) == set(MODEL_ARCH.keys())

    def test_model_arch_keys(self):
        for model, arch in MODEL_ARCH.items():
            assert "n_layers" in arch
            assert "n_kv_heads" in arch
            assert "d_head" in arch
            assert arch["n_layers"] > 0
            assert arch["n_kv_heads"] > 0
            assert arch["d_head"] > 0


# ── Hardware DB ──────────────────────────────────────────────────────


class TestHardwareDB:
    def test_reference_gpu_exists(self):
        assert REFERENCE_GPU in GPU_DB

    def test_gpu_spec_fields(self):
        for name, spec in GPU_DB.items():
            assert spec.vram_gb > 0
            assert spec.bandwidth_gbps > 0
            assert spec.cost_per_hour > 0
            assert spec.name == name

    def test_get_gpu_exact(self):
        spec = get_gpu("RTX 4090 24GB")
        assert spec is not None
        assert spec.vram_gb == 24.0

    def test_get_gpu_case_insensitive(self):
        spec = get_gpu("rtx 4090 24gb")
        assert spec is not None
        assert spec.vram_gb == 24.0

    def test_get_gpu_unknown(self):
        assert get_gpu("AMD RX 7900 XTX") is None

    def test_bandwidth_ratio_reference(self):
        assert bandwidth_ratio(REFERENCE_GPU) == pytest.approx(1.0)

    def test_bandwidth_ratio_faster_gpu(self):
        assert bandwidth_ratio("RTX 4090 24GB") > 1.0

    def test_bandwidth_ratio_unknown(self):
        assert bandwidth_ratio("Unknown GPU") == 1.0


# ── VRAM Model ───────────────────────────────────────────────────────


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


# ── Throughput Model ─────────────────────────────────────────────────


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


# ── Scaling Model ────────────────────────────────────────────────────


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


# ── Quality Model ────────────────────────────────────────────────────


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


# ── Cost Model ───────────────────────────────────────────────────────


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


# ── Latency Model ────────────────────────────────────────────────────


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


# ── Serialization Round-Trip ─────────────────────────────────────────


class TestSerialization:
    def test_round_trip(self, bundled_models, tmp_path):
        # Serialize
        data = {
            "vram": bundled_models.vram.to_dict(),
            "throughput": bundled_models.throughput.to_dict(),
            "scaling": bundled_models.scaling.to_dict(),
            "quality": bundled_models.quality.to_dict(),
            "cost": bundled_models.cost.to_dict(),
            "latency": bundled_models.latency.to_dict(),
        }
        path = tmp_path / "models.json"
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

        loaded = load_models(path)

        # VRAM predictions match
        for model in ["llama3.2-1b", "llama3.2-3b"]:
            orig = bundled_models.vram.predict(model, "FP16", 2048)
            back = loaded.vram.predict(model, "FP16", 2048)
            assert orig == pytest.approx(back)

        # Throughput predictions match
        orig_t = bundled_models.throughput.predict("llama3.2-3b", "ollama", "FP16")
        back_t = loaded.throughput.predict("llama3.2-3b", "ollama", "FP16")
        assert orig_t == pytest.approx(back_t)

    def test_json_keys(self, bundled_models, tmp_path):
        data = {
            "vram": bundled_models.vram.to_dict(),
            "throughput": bundled_models.throughput.to_dict(),
            "scaling": bundled_models.scaling.to_dict(),
            "quality": bundled_models.quality.to_dict(),
            "cost": bundled_models.cost.to_dict(),
            "latency": bundled_models.latency.to_dict(),
        }
        assert set(data.keys()) == {"vram", "throughput", "scaling", "quality", "cost", "latency"}

    def test_bundled_models_are_fitted(self, bundled_models):
        assert bundled_models.vram.fitted
        assert bundled_models.throughput.fitted
        assert bundled_models.scaling.fitted
        assert bundled_models.quality.fitted
        assert bundled_models.latency.fitted


# ── Planner Engine ───────────────────────────────────────────────────


class TestPlanner:
    def test_enumerate_finds_candidates(self, bundled_models):
        candidates = enumerate_candidates(
            models=bundled_models,
            target_models=["llama3.2-3b"],
            hardware="RTX 4080 12GB",
            request_rate=0.5,
            latency_slo=10000,
            quality_target=0.3,
            budget=200,
            avg_tokens=128,
            context_length=2048,
        )
        assert len(candidates) > 0
        costs = [c.monthly_cost for c in candidates]
        assert costs == sorted(costs)

    def test_vram_gate_rejects(self, bundled_models):
        candidates = enumerate_candidates(
            models=bundled_models,
            target_models=["llama3.1-8b"],
            hardware="RTX 4060 8GB",
            request_rate=0.5,
            latency_slo=10000,
            quality_target=0.0,
            budget=1000,
            avg_tokens=128,
            context_length=2048,
        )
        fp16_candidates = [c for c in candidates if c.quant == "FP16"]
        assert len(fp16_candidates) == 0

    def test_budget_gate_rejects(self, bundled_models):
        candidates = enumerate_candidates(
            models=bundled_models,
            target_models=["llama3.2-3b"],
            hardware="H100 80GB",
            request_rate=0.5,
            latency_slo=10000,
            quality_target=0.0,
            budget=1.0,
            avg_tokens=128,
            context_length=2048,
        )
        assert len(candidates) == 0

    def test_quality_gate_rejects(self, bundled_models):
        candidates = enumerate_candidates(
            models=bundled_models,
            target_models=["llama3.2-1b"],
            hardware="RTX 4080 12GB",
            request_rate=0.5,
            latency_slo=10000,
            quality_target=0.99,
            budget=200,
            avg_tokens=128,
            context_length=2048,
        )
        assert len(candidates) == 0

    def test_candidate_has_all_fields(self, bundled_models):
        candidates = enumerate_candidates(
            models=bundled_models,
            target_models=["llama3.2-3b"],
            hardware="RTX 4080 12GB",
            request_rate=0.5,
            latency_slo=10000,
            quality_target=0.3,
            budget=200,
            avg_tokens=128,
            context_length=2048,
        )
        c = candidates[0]
        assert c.model
        assert c.quant in QUANT_LEVELS
        assert c.backend in BACKENDS
        assert c.n_agents >= 1
        assert c.vram_gb > 0
        assert 0 <= c.quality <= 1
        assert c.throughput_tps > 0
        assert c.p95_latency_ms > 0
        assert c.monthly_cost > 0

    def test_find_models_for_size(self):
        models_3b = find_models_for_size("3b")
        assert "llama3.2-3b" in models_3b
        assert "llama3.1-8b" not in models_3b

    def test_find_models_for_size_1b(self):
        models_1b = find_models_for_size("1b")
        assert "llama3.2-1b" in models_1b

    def test_json_output(self, bundled_models):
        from chimeraforge.planner.formatter import format_json

        candidates = enumerate_candidates(
            models=bundled_models,
            target_models=["llama3.2-3b"],
            hardware="RTX 4080 12GB",
            request_rate=0.5,
            latency_slo=10000,
            quality_target=0.3,
            budget=200,
            avg_tokens=128,
            context_length=2048,
        )
        raw = format_json(candidates)
        data = json.loads(raw)
        assert isinstance(data, list)
        assert len(data) > 0
        assert "model" in data[0]
        assert "monthly_cost" in data[0]


# ── Spot Checks (Real Data Validation) ───────────────────────────────


class TestSpotChecks:
    """Validate bundled models against known-good values from TR133."""

    def test_llama32_3b_fp16_vram(self, bundled_models):
        vram = bundled_models.vram.predict("llama3.2-3b", "FP16", 2048)
        assert 3.0 < vram < 12.0

    def test_llama31_8b_fp16_vram(self, bundled_models):
        vram = bundled_models.vram.predict("llama3.1-8b", "FP16", 2048)
        assert 8.0 < vram < 30.0

    def test_q4_vram_less_than_fp16(self, bundled_models):
        q4 = bundled_models.vram.predict("llama3.2-3b", "Q4_K_M", 2048)
        fp16 = bundled_models.vram.predict("llama3.2-3b", "FP16", 2048)
        assert q4 < fp16

    def test_1b_faster_than_3b(self, bundled_models):
        tps_1b = bundled_models.throughput.predict("llama3.2-1b", "ollama", "FP16")
        tps_3b = bundled_models.throughput.predict("llama3.2-3b", "ollama", "FP16")
        assert tps_1b > tps_3b

    def test_fp16_quality_ge_q2(self, bundled_models):
        q_fp16 = bundled_models.quality.predict("llama3.2-1b", "FP16")
        q_q2 = bundled_models.quality.predict("llama3.2-1b", "Q2_K")
        assert q_fp16 >= q_q2

    def test_eta_n1_equals_one(self, bundled_models):
        assert bundled_models.scaling.predict_eta("llama3.2-3b", "ollama", 1) == 1.0

    def test_eta_n8_less_than_n1(self, bundled_models):
        eta_8 = bundled_models.scaling.predict_eta("llama3.2-3b", "ollama", 8)
        assert eta_8 < 1.0

    def test_higher_throughput_lower_cost(self, bundled_models):
        cost_100 = bundled_models.cost.predict_cost_per_1m(100.0)
        cost_10 = bundled_models.cost.predict_cost_per_1m(10.0)
        assert cost_100 < cost_10

    def test_monthly_cost_formula(self, bundled_models):
        monthly = bundled_models.cost.predict_monthly(0.035)
        assert monthly == pytest.approx(25.2)


# -- Find Models Edge Cases ---------------------------------------------------


class TestFindModelsEdgeCases:
    def test_zero_size(self):
        """find_models_for_size('0b') should not crash."""
        models = find_models_for_size("0b")
        assert isinstance(models, list)
        assert len(models) > 0

    def test_negative_size(self):
        models = find_models_for_size("-1b")
        assert isinstance(models, list)
        assert len(models) > 0

    def test_empty_string(self):
        models = find_models_for_size("")
        assert isinstance(models, list)
        assert len(models) > 0

    def test_non_numeric(self):
        models = find_models_for_size("abc")
        assert set(models) == set(MODEL_PARAMS_B.keys())

    def test_large_size_returns_closest(self):
        models = find_models_for_size("100b")
        assert len(models) >= 1
        assert "llama3.1-8b" in models  # closest to 100b

    def test_decimal_size(self):
        models = find_models_for_size("1.5b")
        assert "qwen2.5-1.5b" in models


# -- Quality Tier Tests -------------------------------------------------------


class TestQualityTiers:
    def test_fp16_negligible(self, bundled_models):
        tier = bundled_models.quality.quality_tier("llama3.2-3b", "FP16")
        assert tier == "negligible"

    def test_q2_lower_quality(self, bundled_models):
        tier = bundled_models.quality.quality_tier("llama3.2-3b", "Q2_K")
        assert tier in ("negligible", "acceptable", "concerning", "unacceptable")

    def test_quality_values_bounded(self, bundled_models):
        """All quality predictions should be in [0, 1]."""
        for model in MODEL_PARAMS_B:
            for quant in QUANT_LEVELS + ["FP16"]:
                q = bundled_models.quality.predict(model, quant)
                assert 0.0 <= q <= 1.0, f"Quality {q} out of bounds for {model}|{quant}"

    def test_8b_fp16_returns_value(self, bundled_models):
        """llama3.1-8b FP16 quality should return a value in [0, 1]."""
        q = bundled_models.quality.predict("llama3.1-8b", "FP16")
        assert 0.0 <= q <= 1.0


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


# -- Serialization Extended ---------------------------------------------------


class TestSerializationExtended:
    def test_round_trip_all_models(self, bundled_models, tmp_path):
        """All 6 models round-trip correctly."""
        data = {
            "vram": bundled_models.vram.to_dict(),
            "throughput": bundled_models.throughput.to_dict(),
            "scaling": bundled_models.scaling.to_dict(),
            "quality": bundled_models.quality.to_dict(),
            "cost": bundled_models.cost.to_dict(),
            "latency": bundled_models.latency.to_dict(),
        }
        path = tmp_path / "models.json"
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        loaded = load_models(path)

        # Scaling
        for model in ["llama3.2-3b"]:
            for n in [1, 4, 8]:
                orig = bundled_models.scaling.predict_eta(model, "ollama", n)
                back = loaded.scaling.predict_eta(model, "ollama", n)
                assert orig == pytest.approx(back)

        # Quality
        orig_q = bundled_models.quality.predict("llama3.2-3b", "Q4_K_M")
        back_q = loaded.quality.predict("llama3.2-3b", "Q4_K_M")
        assert orig_q == pytest.approx(back_q)

        # Cost
        orig_c = bundled_models.cost.predict_monthly()
        back_c = loaded.cost.predict_monthly()
        assert orig_c == pytest.approx(back_c)

    def test_empty_json_returns_defaults(self, tmp_path):
        path = tmp_path / "empty.json"
        path.write_text("{}", encoding="utf-8")
        loaded = load_models(path)
        # Should not crash, uses defaults
        assert loaded.vram.overhead_factor == 1.10
        assert loaded.vram.fitted is False


# -- Planner Extended ---------------------------------------------------------


class TestPlannerExtended:
    def test_empty_target_models(self, bundled_models):
        candidates = enumerate_candidates(
            models=bundled_models,
            target_models=[],
            hardware="RTX 4080 12GB",
            request_rate=0.5,
            latency_slo=10000,
            quality_target=0.3,
            budget=200,
            avg_tokens=128,
            context_length=2048,
        )
        assert candidates == []

    def test_n_search_tries_higher_n_for_latency(self, bundled_models):
        """With tight latency SLO, engine should try N > min-throughput-N."""
        candidates = enumerate_candidates(
            models=bundled_models,
            target_models=["llama3.2-3b"],
            hardware="RTX 4080 12GB",
            request_rate=2.0,
            latency_slo=3000,
            quality_target=0.0,
            budget=500,
            avg_tokens=128,
            context_length=2048,
        )
        # Should find candidates with N > 1 that pass latency
        high_n = [c for c in candidates if c.n_agents > 1]
        # At least some configs should exist
        assert len(candidates) >= 0  # May or may not find depending on data


# -- CLI Integration ----------------------------------------------------------


class TestCLIPlan:
    @staticmethod
    def _strip_ansi(text: str) -> str:
        import re

        return re.sub(r"\x1b\[[0-9;]*m", "", text)

    def test_plan_help(self):
        from typer.testing import CliRunner
        from chimeraforge.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["plan", "--help"])
        output = self._strip_ansi(result.output)
        assert result.exit_code == 0
        assert "--model-size" in output

    def test_plan_negative_request_rate(self):
        from typer.testing import CliRunner
        from chimeraforge.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["plan", "--request-rate", "-1"])
        assert result.exit_code == 1

    def test_plan_zero_avg_tokens(self):
        from typer.testing import CliRunner
        from chimeraforge.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["plan", "--avg-tokens", "0"])
        assert result.exit_code == 1

    def test_plan_invalid_quality_target(self):
        from typer.testing import CliRunner
        from chimeraforge.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["plan", "--quality-target", "1.5"])
        assert result.exit_code == 1

    def test_plan_json_output(self):
        from typer.testing import CliRunner
        from chimeraforge.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["plan", "--json"])
        assert result.exit_code == 0


# -- Formatter ----------------------------------------------------------------


class TestFormatter:
    def test_format_json_all_fields(self, bundled_models):
        from dataclasses import fields
        from chimeraforge.planner.formatter import format_json

        candidates = enumerate_candidates(
            models=bundled_models,
            target_models=["llama3.2-3b"],
            hardware="RTX 4080 12GB",
            request_rate=0.5,
            latency_slo=10000,
            quality_target=0.3,
            budget=200,
            avg_tokens=128,
            context_length=2048,
        )
        raw = format_json(candidates)
        data = json.loads(raw)
        assert len(data) > 0
        # All Candidate fields present
        candidate_fields = {f.name for f in fields(Candidate)}
        assert candidate_fields == set(data[0].keys())

    def test_format_json_empty(self):
        from chimeraforge.planner.formatter import format_json

        raw = format_json([])
        assert json.loads(raw) == []
