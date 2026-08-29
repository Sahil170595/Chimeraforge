"""Tests for Mixture-of-Experts support (active vs total parameters).

The load-bearing claim is that VRAM sizes on TOTAL params (every expert is
resident) while throughput and TTFT scale with ACTIVE params (a token only reads
the experts it routed to). Getting this wrong under-predicts an MoE model's
throughput by the active/total ratio -- 3.6x on Mixtral, ~18x on DeepSeek-V3.

The active-param derivation is checked against published figures, so these are
falsifiability gates, not self-consistency checks.
"""

from __future__ import annotations

import pytest

from chimeraforge.planner.engine import enumerate_candidates
from chimeraforge.planner.resolver import (
    SOURCE_HF,
    ModelSpec,
    moe_from_config,
    spec_from_hf,
)

# Real config.json field sets, trimmed to what the resolver reads.
MIXTRAL_CFG = dict(
    num_hidden_layers=32,
    num_attention_heads=32,
    num_key_value_heads=8,
    hidden_size=4096,
    num_local_experts=8,
    num_experts_per_tok=2,
    intermediate_size=14336,
    model_type="mixtral",
)
DEEPSEEK_CFG = dict(
    num_hidden_layers=61,
    num_attention_heads=128,
    num_key_value_heads=128,
    hidden_size=7168,
    n_routed_experts=256,
    num_experts_per_tok=8,
    moe_intermediate_size=2048,
    first_k_dense_replace=3,
    intermediate_size=18432,
    model_type="deepseek_v3",
)
QWEN_MOE_CFG = dict(
    num_hidden_layers=48,
    num_attention_heads=32,
    num_key_value_heads=4,
    hidden_size=2048,
    num_experts=128,
    num_experts_per_tok=8,
    moe_intermediate_size=768,
    model_type="qwen3_moe",
)
DENSE_CFG = dict(
    num_hidden_layers=32,
    num_attention_heads=32,
    num_key_value_heads=8,
    hidden_size=4096,
    intermediate_size=14336,
    model_type="llama",
)


def _moe_spec(**over) -> ModelSpec:
    base = dict(
        name="mixtral-8x7b",
        params_b=46.7,
        n_layers=32,
        n_kv_heads=8,
        d_head=128,
        hidden_size=4096,
        num_experts=8,
        experts_per_token=2,
        moe_intermediate_size=14336,
        source=SOURCE_HF,
    )
    base.update(over)
    return ModelSpec(**base)


class TestActiveParamsGroundTruth:
    """Derivation vs published active-parameter counts (the falsifiability gate)."""

    @pytest.mark.parametrize(
        "cfg,total,published,tol",
        [
            (MIXTRAL_CFG, 46.7, 12.9, 0.1),  # Mixtral-8x7B
            (DEEPSEEK_CFG, 671.0, 37.0, 1.0),  # DeepSeek-V3
            (QWEN_MOE_CFG, 30.5, 3.3, 0.1),  # Qwen3-30B-A3B
        ],
    )
    def test_matches_published_active_count(self, cfg, total, published, tol):
        spec = spec_from_hf("org/model", cfg, total)
        assert spec.is_moe
        assert spec.active_params_b == pytest.approx(published, abs=tol)

    def test_active_is_strictly_less_than_total(self):
        assert _moe_spec().active_params_b < 46.7


class TestDenseUnaffected:
    def test_dense_active_equals_total(self):
        spec = spec_from_hf("meta-llama/Llama-3.1-8B", DENSE_CFG, 8.03)
        assert not spec.is_moe
        assert spec.active_params_b == spec.params_b

    def test_dense_intermediate_size_not_mistaken_for_expert(self):
        # DENSE_CFG has intermediate_size but no expert count -> must stay dense.
        assert moe_from_config(DENSE_CFG) == {}

    def test_registry_models_are_dense(self):
        spec = ModelSpec.from_registry("llama3.1-8b")
        assert not spec.is_moe
        assert spec.active_params_b == spec.params_b


class TestConfigParsing:
    def test_mixtral_keys(self):
        m = moe_from_config(MIXTRAL_CFG)
        assert m["num_experts"] == 8 and m["experts_per_token"] == 2

    def test_deepseek_keys_incl_dense_prefix(self):
        m = moe_from_config(DEEPSEEK_CFG)
        assert m["num_experts"] == 256
        assert m["moe_intermediate_size"] == 2048  # not intermediate_size (18432)
        assert m["n_dense_layers"] == 3

    def test_qwen_keys(self):
        m = moe_from_config(QWEN_MOE_CFG)
        assert m["num_experts"] == 128 and m["experts_per_token"] == 8

    def test_experts_without_topk_is_not_moe(self):
        assert moe_from_config({"num_experts": 8}) == {}


class TestDegradesToDense:
    """Incomplete geometry must fall back to TOTAL -- the conservative answer.

    A wrong guess here inflates predicted throughput, which is the failure mode
    that matters; reporting the dense number is honest and safe.
    """

    def test_missing_hidden_size_falls_back(self):
        assert _moe_spec(hidden_size=None).active_params_b == 46.7

    def test_missing_expert_width_falls_back(self):
        assert _moe_spec(moe_intermediate_size=None).active_params_b == 46.7

    def test_topk_equal_to_experts_is_not_moe(self):
        # Every expert active per token == dense, not MoE.
        spec = _moe_spec(experts_per_token=8)
        assert not spec.is_moe
        assert spec.active_params_b == 46.7

    def test_all_layers_dense_falls_back(self):
        assert _moe_spec(n_dense_layers=32).active_params_b == 46.7

    def test_absurd_geometry_never_returns_negative(self):
        # Over-large experts would drive active below zero; clamp to total instead.
        spec = _moe_spec(moe_intermediate_size=10**6)
        assert spec.active_params_b > 0

    def test_serialization_round_trip_preserves_moe(self):
        spec = _moe_spec()
        back = ModelSpec.from_dict(spec.to_dict())
        assert back.is_moe
        assert back.active_params_b == spec.active_params_b

    def test_legacy_cached_spec_without_moe_fields_loads_dense(self):
        # Specs cached before 0.14.0 have no MoE keys -> defaults -> dense.
        legacy = {"name": "x", "params_b": 8.0, "n_layers": 32, "n_kv_heads": 8, "d_head": 128}
        back = ModelSpec.from_dict(legacy)
        assert not back.is_moe
        assert back.active_params_b == 8.0


class TestEngineUsesTheRightCount:
    def _plan(self, spec):
        from chimeraforge.planner.models import load_bundled_models

        return enumerate_candidates(
            models=load_bundled_models(),
            target_models=[spec.name],
            hardware="H100 80GB",
            request_rate=1.0,
            latency_slo=60000,
            quality_target=0.0,
            budget=1e9,
            avg_tokens=128,
            context_length=2048,
            specs={spec.name: spec},
        )

    def test_vram_sizes_on_total_throughput_on_active(self):
        moe = self._plan(_moe_spec())
        # Same model with the MoE geometry stripped == the pre-0.14.0 treatment.
        dense = self._plan(
            _moe_spec(num_experts=None, experts_per_token=None, moe_intermediate_size=None)
        )
        assert moe and dense
        # Compare the SAME cell, not the two winners. Comparing winners assumed
        # both searches pick the same quant, which is not a property of MoE
        # geometry -- reordering the quant ladder by measured width was enough to
        # break it, with nothing about VRAM having changed.
        by_cell = {(c.quant, c.backend): c for c in dense}
        shared = [c for c in moe if (c.quant, c.backend) in by_cell]
        assert shared, "no cell in common between the MoE and dense plans"
        for m in shared:
            d = by_cell[(m.quant, m.backend)]
            # Every expert is resident either way -> identical VRAM.
            assert m.vram_gb == pytest.approx(d.vram_gb), f"{m.quant}/{m.backend}"
        # Only the routed experts are read -> materially faster decode + prefill.
        assert m.throughput_tps > d.throughput_tps * 2
        assert m.ttft_ms < d.ttft_ms

    def test_candidate_exposes_both_counts(self):
        c = self._plan(_moe_spec())[0]
        assert c.params_b == pytest.approx(46.7)
        assert c.active_params_b < c.params_b

    def test_dense_candidate_active_equals_total(self):
        c = self._plan(
            _moe_spec(num_experts=None, experts_per_token=None, moe_intermediate_size=None)
        )[0]
        assert c.active_params_b == pytest.approx(c.params_b)

    def test_moe_warning_is_surfaced(self):
        c = self._plan(_moe_spec())[0]
        assert any("MoE" in w and "active per token" in w for w in c.warnings)

    def test_no_moe_warning_on_dense(self):
        c = self._plan(
            _moe_spec(num_experts=None, experts_per_token=None, moe_intermediate_size=None)
        )[0]
        assert not any("MoE" in w for w in c.warnings)
