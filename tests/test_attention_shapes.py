"""Tests for attention-shape-aware KV-cache sizing (MLA and sliding-window).

The planner's default KV formula assumes MHA/GQA: ``2 (K+V) * kv_heads * d_head``
elements per token per layer. Two families break that badly enough to change the
answer:

- **MLA** (DeepSeek-V2/V3) caches one compressed latent plus a decoupled RoPE key.
  Applying the GQA formula to DeepSeek-V3 overstates its cache by ~57x, which
  rejects fleets that would actually have fit.
- **Sliding-window attention** stops the cache growing past the window on local
  layers.

The safety property runs the other way: a window whose layer pattern is unknown is
NOT applied, because under-sizing KV is what turns "it fits" into an OOM.
"""

from __future__ import annotations

import pytest

from chimeraforge.planner.models import VRAMModel
from chimeraforge.planner.resolver import ModelSpec, attention_from_config, spec_from_hf

# Real config.json field sets, trimmed to what the resolver reads.
DEEPSEEK_V3_CFG = dict(
    num_hidden_layers=61,
    num_attention_heads=128,
    num_key_value_heads=128,
    hidden_size=7168,
    n_routed_experts=256,
    num_experts_per_tok=8,
    moe_intermediate_size=2048,
    first_k_dense_replace=3,
    kv_lora_rank=512,
    qk_rope_head_dim=64,
    model_type="deepseek_v3",
)
GEMMA3_CFG = dict(
    num_hidden_layers=48,
    num_attention_heads=16,
    num_key_value_heads=8,
    hidden_size=3840,
    sliding_window=1024,
    sliding_window_pattern=6,
    model_type="gemma3",
)
MISTRAL_CFG = dict(
    num_hidden_layers=32,
    num_attention_heads=32,
    num_key_value_heads=8,
    hidden_size=4096,
    sliding_window=4096,
    model_type="mistral",
)
LLAMA_CFG = dict(
    num_hidden_layers=32,
    num_attention_heads=32,
    num_key_value_heads=8,
    hidden_size=4096,
    model_type="llama",
)

GQA_ARCH = {"n_layers": 32, "n_kv_heads": 8, "d_head": 128}


@pytest.fixture(scope="module")
def vram():
    return VRAMModel()


def _dense(**over) -> ModelSpec:
    base = dict(name="dense", params_b=8.03, n_layers=32, n_kv_heads=8, d_head=128)
    base.update(over)
    return ModelSpec(**base)


class TestMlaCacheShape:
    def test_deepseek_v3_latent_width_is_first_principles(self):
        # kv_lora_rank (512) + qk_rope_head_dim (64) = 576 elements per layer/token,
        # against 2 * 128 * 128 = 32,768 under the GQA formula.
        spec = spec_from_hf("deepseek-ai/DeepSeek-V3", DEEPSEEK_V3_CFG, 671.0)
        assert spec.is_mla
        assert spec.kv_elems_per_token_per_layer == 576

    def test_mla_cache_is_dramatically_smaller(self, vram):
        spec = spec_from_hf("deepseek-ai/DeepSeek-V3", DEEPSEEK_V3_CFG, 671.0)
        gqa_arch = {"n_layers": 61, "n_kv_heads": 128, "d_head": 128}
        mla_gb = vram.kv_cache_gb(spec.arch(), 8192)
        gqa_gb = vram.kv_cache_gb(gqa_arch, 8192)
        assert gqa_gb / mla_gb == pytest.approx(32768 / 576, rel=0.01)
        assert mla_gb < 1.0 < gqa_gb  # 0.54 GB vs 30.5 GB

    def test_mla_needs_both_fields(self):
        # A lora rank alone is not enough to know the cache shape.
        assert not _dense(kv_lora_rank=512).is_mla
        assert not _dense(qk_rope_head_dim=64).is_mla

    def test_partial_mla_falls_back_to_gqa(self):
        spec = _dense(kv_lora_rank=512)
        assert spec.kv_elems_per_token_per_layer == 2 * 8 * 128

    def test_mla_still_reports_moe_active_params(self):
        # The two 0.14.0/0.18.0 features must compose on the same model.
        spec = spec_from_hf("deepseek-ai/DeepSeek-V3", DEEPSEEK_V3_CFG, 671.0)
        assert spec.is_moe and spec.is_mla
        assert spec.active_params_b == pytest.approx(37.0, abs=1.0)


class TestSlidingWindow:
    def test_window_with_pattern_shrinks_cache(self, vram):
        spec = spec_from_hf("google/gemma-3-12b-it", GEMMA3_CFG, 12.2)
        full = {"n_layers": 48, "n_kv_heads": 8, "d_head": 128}
        assert vram.kv_cache_gb(spec.arch(), 8192) < vram.kv_cache_gb(full, 8192)

    def test_effective_context_is_the_layer_weighted_mix(self, vram):
        # 48 layers, 1-in-6 global: 8 layers see 8192, 40 see 1024.
        spec = spec_from_hf("google/gemma-3-12b-it", GEMMA3_CFG, 12.2)
        expected_ctx = (8 * 8192 + 40 * 1024) / 48
        d_head = 3840 // 16  # head_dim absent from config -> hidden / n_heads
        expected_gb = 48 * expected_ctx * (2 * 8 * d_head) * 2 / (1024**3)
        assert vram.kv_cache_gb(spec.arch(), 8192) == pytest.approx(expected_gb)

    def test_window_larger_than_context_changes_nothing(self, vram):
        spec = _dense(sliding_window=8192, swa_global_every=6)
        assert vram.kv_cache_gb(spec.arch(), 2048) == pytest.approx(
            vram.kv_cache_gb(GQA_ARCH, 2048)
        )

    def test_layer_types_list_derives_the_pattern(self):
        cfg = dict(GEMMA3_CFG)
        cfg.pop("sliding_window_pattern")
        cfg["layer_types"] = ["sliding_attention"] * 5 + ["full_attention"]
        assert attention_from_config(cfg)["swa_global_every"] == 6


class TestConservativeWhenPatternUnknown:
    """Under-sizing KV is the dangerous direction, so an unplaceable window is dropped."""

    def test_mistral_window_without_pattern_is_not_applied(self):
        spec = spec_from_hf("mistralai/Mistral-7B-v0.1", MISTRAL_CFG, 7.24)
        assert spec.sliding_window == 4096
        assert spec.swa_global_every == 0
        assert "swa_window" not in spec.arch()

    def test_unpatterned_window_gives_full_context_cache(self, vram):
        spec = _dense(sliding_window=1024)
        assert vram.kv_cache_gb(spec.arch(), 8192) == pytest.approx(
            vram.kv_cache_gb(GQA_ARCH, 8192)
        )


class TestDenseUnchanged:
    def test_plain_model_has_no_special_shape(self):
        spec = spec_from_hf("meta-llama/Llama-3.1-8B", LLAMA_CFG, 8.03)
        assert not spec.is_mla and not spec.sliding_window

    def test_cache_matches_the_pre_0_18_formula(self, vram):
        spec = spec_from_hf("meta-llama/Llama-3.1-8B", LLAMA_CFG, 8.03)
        assert vram.kv_cache_gb(spec.arch(), 8192) == pytest.approx(
            vram.kv_cache_gb(GQA_ARCH, 8192)
        )

    def test_bare_arch_dict_still_works(self, vram):
        # Library callers pass a plain arch dict with no shape hints.
        assert vram.kv_cache_gb(GQA_ARCH, 2048) > 0

    def test_registry_models_unaffected(self, vram):
        spec = ModelSpec.from_registry("llama3.1-8b")
        assert not spec.is_mla and "swa_window" not in spec.arch()

    def test_legacy_cached_spec_loads_without_shape_fields(self):
        legacy = {"name": "x", "params_b": 8.0, "n_layers": 32, "n_kv_heads": 8, "d_head": 128}
        back = ModelSpec.from_dict(legacy)
        assert not back.is_mla and back.kv_elems_per_token_per_layer == 2 * 8 * 128

    def test_round_trip_preserves_shape(self):
        spec = spec_from_hf("deepseek-ai/DeepSeek-V3", DEEPSEEK_V3_CFG, 671.0)
        back = ModelSpec.from_dict(spec.to_dict())
        assert back.is_mla
        assert back.kv_elems_per_token_per_layer == spec.kv_elems_per_token_per_layer


class TestConfigParsing:
    def test_plain_config_declares_nothing(self):
        assert attention_from_config(LLAMA_CFG) == {}

    def test_mla_keys(self):
        got = attention_from_config(DEEPSEEK_V3_CFG)
        assert got["kv_lora_rank"] == 512 and got["qk_rope_head_dim"] == 64

    def test_swa_keys(self):
        got = attention_from_config(GEMMA3_CFG)
        assert got["sliding_window"] == 1024 and got["swa_global_every"] == 6


class TestEngineIntegration:
    def _plan(self, spec, **over):
        from chimeraforge.planner.engine import enumerate_candidates
        from chimeraforge.planner.models import load_bundled_models

        kw = dict(
            models=load_bundled_models(),
            target_models=[spec.name],
            hardware="H200 141GB",
            request_rate=1.0,
            latency_slo=60000,
            quality_target=0.0,
            budget=1e9,
            avg_tokens=128,
            context_length=8192,
            specs={spec.name: spec},
            tensor_parallel=8,  # 671B needs a group; TP=1 fits nothing on one card
        )
        kw.update(over)
        return enumerate_candidates(**kw)

    def test_mla_model_warns_about_its_cache_shape(self):
        spec = spec_from_hf("deepseek-v3", DEEPSEEK_V3_CFG, 671.0)
        cands = self._plan(spec)
        assert cands
        assert any("MLA attention" in w for w in cands[0].warnings)

    def test_swa_model_warns_about_the_window(self):
        spec = spec_from_hf("gemma-3-12b", GEMMA3_CFG, 12.2)
        cands = self._plan(spec)
        assert cands
        assert any("sliding-window attention" in w for w in cands[0].warnings)

    def test_unpatterned_window_says_it_is_conservative(self):
        spec = spec_from_hf("mistral-7b", MISTRAL_CFG, 7.24)
        cands = self._plan(spec)
        assert cands
        assert any("no layer pattern" in w for w in cands[0].warnings)

    def test_dense_model_gets_no_attention_warning(self):
        spec = spec_from_hf("llama-3.1-8b", LLAMA_CFG, 8.03)
        cands = self._plan(spec)
        assert cands
        assert not any("MLA" in w or "sliding-window" in w for w in cands[0].warnings)

    def test_mla_raises_the_concurrency_ceiling(self):
        # A smaller per-sequence cache means more sequences fit in the same VRAM,
        # which is the practical consequence of getting the shape right.
        spec = spec_from_hf("deepseek-v3", DEEPSEEK_V3_CFG, 671.0)
        as_gqa = ModelSpec(**{**spec.to_dict(), "kv_lora_rank": None, "qk_rope_head_dim": None})
        mla = self._plan(spec)
        gqa = self._plan(as_gqa)
        assert mla and gqa, "both variants must plan, or this proves nothing"
        # Measured: 503 concurrent sequences under MLA vs 20 under the GQA formula.
        assert mla[0].max_concurrent_seqs > gqa[0].max_concurrent_seqs * 5
