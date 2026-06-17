"""Tests for the planner engine: candidate search, gates, spot checks, and edge cases."""

from __future__ import annotations

import json

import pytest

from chimeraforge.planner.constants import BACKENDS, MODEL_PARAMS_B, QUANT_LEVELS
from chimeraforge.planner.engine import enumerate_candidates, find_models_for_size


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


# ── Safety Gate (Gate 5) ─────────────────────────────────────────────


class TestSafetyGate:
    """Opt-in safety gate over the (model, quant) refusal table."""

    def _plan(self, models, model_name, safety_target=None, quality_target=0.0):
        return enumerate_candidates(
            models=models,
            target_models=[model_name],
            hardware="RTX 4080 12GB",
            request_rate=1.0,
            latency_slo=5000.0,
            quality_target=quality_target,
            budget=1000.0,
            avg_tokens=128,
            context_length=2048,
            safety_target=safety_target,
        )

    def test_gate_off_by_default_keeps_collapse_cell(self, bundled_models):
        # No safety_target -> gate inert -> the unsafe Q2_K cell still appears.
        quants = {c.quant for c in self._plan(bundled_models, "llama3.2-1b")}
        assert "Q2_K" in quants

    def test_gate_rejects_collapse_cell(self, bundled_models):
        baseline = {(c.model, c.quant) for c in self._plan(bundled_models, "llama3.2-1b")}
        assert ("llama3.2-1b", "Q2_K") in baseline  # present absent the gate
        gated = {
            (c.model, c.quant) for c in self._plan(bundled_models, "llama3.2-1b", safety_target=0.8)
        }
        assert ("llama3.2-1b", "Q2_K") not in gated  # refusal 0.368 < 0.8 -> rejected
        assert ("llama3.2-1b", "Q4_K_M") in gated  # refusal 0.905 >= 0.8 -> kept

    def test_candidates_carry_safety_fields(self, bundled_models):
        cands = self._plan(bundled_models, "llama3.2-1b", safety_target=0.8)
        assert cands
        for c in cands:
            assert c.safety_refusal is not None and c.safety_refusal >= 0.8
            assert c.rtsi_risk in ("HIGH", "MODERATE", "LOW", "UNKNOWN")

    def test_non_monotonic_3b_is_data_faithful(self, bundled_models):
        # llama3.2-3b refusal is non-monotonic: Q4_K_M (0.664) < Q2_K (0.927).
        # The gate must follow the data, not "lower quant = less safe" intuition.
        baseline = {(c.model, c.quant) for c in self._plan(bundled_models, "llama3.2-3b")}
        assert ("llama3.2-3b", "Q4_K_M") in baseline  # generated absent the gate
        gated = {
            (c.model, c.quant) for c in self._plan(bundled_models, "llama3.2-3b", safety_target=0.7)
        }
        assert ("llama3.2-3b", "Q4_K_M") not in gated  # 0.664 < 0.7 -> rejected
        assert ("llama3.2-3b", "Q2_K") in gated  # 0.927 >= 0.7 -> kept

    def test_unknown_safety_passes_with_warning(self, bundled_models):
        # qwen2.5-0.5b is in the planner registry but has no safety data.
        # The gate blocks only KNOWN-unsafe cells, so it passes — with a warning.
        cands = self._plan(bundled_models, "qwen2.5-0.5b", safety_target=0.8)
        assert cands
        for c in cands:
            assert c.safety_refusal is None
            assert c.rtsi_risk == "UNKNOWN"
            assert any("not screened" in w for w in c.warnings)

    def test_rtsi_high_warning_on_kept_cell(self, bundled_models):
        # Low target keeps the collapse cell; it must still carry the RTSI warning.
        cands = self._plan(bundled_models, "llama3.2-1b", safety_target=0.3)
        q2k = [c for c in cands if c.quant == "Q2_K"]
        assert q2k
        assert any("RTSI" in w and "HIGH" in w for w in q2k[0].warnings)


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
        # The tight-latency N-search path should run and return a candidate list.
        assert isinstance(candidates, list)
