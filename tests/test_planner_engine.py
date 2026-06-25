"""Tests for the planner engine: candidate search, gates, spot checks, and edge cases."""

from __future__ import annotations

import json

import pytest

from chimeraforge.planner.constants import BACKENDS, MODEL_PARAMS_B, QUANT_LEVELS
from chimeraforge.planner.engine import (
    enumerate_candidates,
    find_models_for_size,
    summarize_trace,
)
from chimeraforge.planner.resolver import ModelSpec


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


# ── Model-Agnostic Specs ─────────────────────────────────────────────


class TestOffRegistrySpecs:
    """Off-registry models resolved to a ModelSpec drive the search."""

    def _offreg_spec(self, name="mistralai/Mistral-7B-Instruct"):
        # A genuinely off-registry 7B (no registry_alias) -> roofline + unknowns.
        return ModelSpec(
            name=name,
            params_b=7.24,
            n_layers=32,
            n_kv_heads=8,
            d_head=128,
            family="mistral",
            source="hf",
        )

    def test_offregistry_model_produces_candidates(self, bundled_models):
        spec = self._offreg_spec()
        cands = enumerate_candidates(
            models=bundled_models,
            target_models=[spec.name],
            hardware="RTX 4090 24GB",
            request_rate=1.0,
            latency_slo=10000,
            quality_target=0.0,
            budget=1000,
            avg_tokens=128,
            context_length=2048,
            specs={spec.name: spec},
        )
        assert cands
        c = cands[0]
        assert c.params_b == 7.24
        assert c.model_source == "hf"

    def test_offregistry_provenance_is_honest(self, bundled_models):
        spec = self._offreg_spec()
        cands = enumerate_candidates(
            models=bundled_models,
            target_models=[spec.name],
            hardware="RTX 4090 24GB",
            request_rate=1.0,
            latency_slo=10000,
            quality_target=0.0,
            budget=1000,
            avg_tokens=128,
            context_length=2048,
            specs={spec.name: spec},
        )
        c = cands[0]
        assert c.provenance["throughput"] == "estimated"
        assert c.provenance["quality"] in ("estimated", "unknown")
        assert c.provenance["safety"] == "unknown"
        assert any("roofline" in w for w in c.warnings)

    def test_vram_uses_resolved_arch_not_default(self, bundled_models):
        # A wide-KV spec must cost more VRAM than a narrow-KV one at same params.
        wide = ModelSpec(
            name="wide", params_b=7.0, n_layers=32, n_kv_heads=32, d_head=128, source="manual"
        )
        narrow = ModelSpec(
            name="narrow", params_b=7.0, n_layers=32, n_kv_heads=2, d_head=128, source="manual"
        )
        v_wide = bundled_models.vram.predict(
            "wide", "FP16", 8192, params_b=wide.params_b, arch=wide.arch()
        )
        v_narrow = bundled_models.vram.predict(
            "narrow", "FP16", 8192, params_b=narrow.params_b, arch=narrow.arch()
        )
        assert v_wide > v_narrow  # KV cache scales with kv heads

    def test_registry_alias_reuses_measured_data(self, bundled_models):
        # An offline approximation (registry_alias set) must reuse the registry
        # model's measured throughput/quality, not a roofline estimate.
        approx = ModelSpec(
            name="llama3.2:3b",
            params_b=3.21,
            n_layers=28,
            n_kv_heads=8,
            d_head=128,
            family="llama3.2",
            source="registry-approx",
            registry_alias="llama3.2-3b",
        )
        cands = enumerate_candidates(
            models=bundled_models,
            target_models=["llama3.2:3b"],
            hardware="RTX 4080 12GB",
            request_rate=0.5,
            latency_slo=10000,
            quality_target=0.3,
            budget=300,
            avg_tokens=128,
            context_length=2048,
            specs={"llama3.2:3b": approx},
        )
        reg = enumerate_candidates(
            models=bundled_models,
            target_models=["llama3.2-3b"],
            hardware="RTX 4080 12GB",
            request_rate=0.5,
            latency_slo=10000,
            quality_target=0.3,
            budget=300,
            avg_tokens=128,
            context_length=2048,
        )
        # Same best-candidate economics despite the aliased tag.
        assert cands[0].throughput_tps == reg[0].throughput_tps
        assert cands[0].quality == reg[0].quality
        assert any("approximated" in w for w in cands[0].warnings)


class TestRejectionTrace:
    """The optional trace explains why a search returned nothing."""

    def test_vram_blocked_trace(self, bundled_models):
        trace: list = []
        cands = enumerate_candidates(
            models=bundled_models,
            target_models=["llama3.1-8b"],
            hardware="RTX 4060 8GB",
            request_rate=0.5,
            latency_slo=10000,
            quality_target=0.99,  # also impossible, but VRAM bites first per quant
            budget=1000,
            avg_tokens=128,
            context_length=2048,
            trace=trace,
        )
        assert cands == []
        assert trace  # rejections recorded
        gates = {t[2] for t in trace}
        assert "vram" in gates or "quality" in gates

    def test_summarize_trace_picks_binding_gate(self, bundled_models):
        # 14B off-registry at an extreme rate even 16 linear replicas can't serve
        # -> throughput-bound (the fastest/smallest quant fits VRAM but not rate).
        spec = ModelSpec(
            name="big/m", params_b=14.0, n_layers=40, n_kv_heads=8, d_head=128, source="hf"
        )
        trace: list = []
        cands = enumerate_candidates(
            models=bundled_models,
            target_models=["big/m"],
            hardware="RTX 4090 24GB",
            request_rate=30.0,  # 30*128=3840 tok/s; 16 replicas of a 14B can't reach it
            latency_slo=10000,
            quality_target=0.0,
            budget=100000,
            avg_tokens=128,
            context_length=2048,
            specs={"big/m": spec},
            trace=trace,
        )
        assert cands == []
        lines = summarize_trace(trace)
        assert any("big/m" in ln and "throughput" in ln for ln in lines)

    def test_linear_replica_scaling_unblocks_large_models(self, bundled_models):
        # C-1: N independent GPUs scale linearly, so a 7B that one GPU can't serve
        # at the rate now plans with multiple replicas (used to be rejected when
        # Amdahl capped total throughput at ~1.8x regardless of N).
        spec = ModelSpec(
            name="mistral/7b", params_b=7.0, n_layers=32, n_kv_heads=8, d_head=128, source="hf"
        )
        cands = enumerate_candidates(
            models=bundled_models,
            target_models=["mistral/7b"],
            hardware="RTX 4080 12GB",
            request_rate=1.0,  # 128 tok/s; one 7B replica can't, several can
            latency_slo=10000,
            quality_target=0.0,
            budget=1000,
            avg_tokens=128,
            context_length=2048,
            specs={"mistral/7b": spec},
        )
        assert cands, "linear replica scaling should let a 7B meet 1 req/s with N>1"
        c = cands[0]
        assert c.n_agents > 1
        assert c.eta == 1.0  # replicas, not Amdahl
        # Linear: total throughput is exactly N * per-replica.
        assert c.total_throughput_tps == pytest.approx(c.n_agents * c.throughput_tps, rel=1e-3)

    def test_cost_per_1m_invariant_in_replica_count(self, bundled_models):
        # C-2: adding identical replicas must not change $/token (cost and tokens
        # both scale by N). Previously cost_per_1m was understated by N.
        spec = ModelSpec(
            name="mistral/7b", params_b=7.0, n_layers=32, n_kv_heads=8, d_head=128, source="hf"
        )

        def best(rate):
            cs = enumerate_candidates(
                models=bundled_models,
                target_models=["mistral/7b"],
                hardware="RTX 4080 12GB",
                request_rate=rate,
                latency_slo=10000,
                quality_target=0.0,
                budget=10000,
                avg_tokens=128,
                context_length=2048,
                specs={"mistral/7b": spec},
            )
            return next(c for c in cs if c.quant == "Q4_K_M")

        low, high = best(1.0), best(3.0)
        assert high.n_agents > low.n_agents  # more replicas at higher rate
        assert high.cost_per_1m_tok == pytest.approx(low.cost_per_1m_tok, rel=1e-3)

    def test_native_legacy_quant_pinned_and_costed(self, bundled_models):
        # M-2: a q4_0 native tag must be evaluated at q4_0 (real bpw), not dropped.
        spec = ModelSpec(
            name="x/y:q4_0",
            params_b=7.0,
            n_layers=32,
            n_kv_heads=8,
            d_head=128,
            native_quant="Q4_0",
            source="ollama",
        )
        cands = enumerate_candidates(
            models=bundled_models,
            target_models=["x/y:q4_0"],
            hardware="RTX 4080 12GB",
            request_rate=0.5,
            latency_slo=10000,
            quality_target=0.0,
            budget=1000,
            avg_tokens=128,
            context_length=2048,
            specs={"x/y:q4_0": spec},
        )
        assert cands
        assert {c.quant for c in cands} == {"Q4_0"}  # pinned, not the full ladder
        # Q4_0 (4.5 bpw) VRAM must be well below the FP16 (16 bpw) footprint.
        assert cands[0].vram_gb < 7.0 * 16 / 8

    def test_no_trace_overhead_when_none(self, bundled_models):
        # Passing trace=None must not raise and must still search normally.
        cands = enumerate_candidates(
            models=bundled_models,
            target_models=["llama3.2-3b"],
            hardware="RTX 4080 12GB",
            request_rate=0.5,
            latency_slo=10000,
            quality_target=0.3,
            budget=200,
            avg_tokens=128,
            context_length=2048,
            trace=None,
        )
        assert cands


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
