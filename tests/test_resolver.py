"""Tests for the model-agnostic spec resolver.

Parser tests use JSON captured from live endpoints (HF Qwen2.5-1.5B config with
``head_dim: null``; a representative Ollama ``/api/show`` GGUF payload) so they
exercise the real-world shapes, not idealised ones. Network fetchers are not
exercised here -- the parse/fetch split keeps the logic testable offline.
"""

from __future__ import annotations

import pytest

from chimeraforge.planner.resolver import (
    SOURCE_MANUAL,
    SOURCE_OLLAMA,
    SOURCE_REGISTRY,
    SOURCE_REGISTRY_APPROX,
    ModelSpec,
    ResolverError,
    parse_param_size,
    resolve_spec,
    spec_from_hf,
    spec_from_ollama_show,
    spec_from_overrides,
)

# Real HF config.json for Qwen/Qwen2.5-1.5B-Instruct (head_dim is null in the wild).
QWEN_CONFIG = {
    "num_hidden_layers": 28,
    "num_attention_heads": 12,
    "num_key_value_heads": 2,
    "hidden_size": 1536,
    "head_dim": None,
    "vocab_size": 151936,
    "torch_dtype": "bfloat16",
    "model_type": "qwen2",
}
QWEN_PARAMS_B = 1543714304 / 1e9  # safetensors.total from the model_info API

# Representative Ollama /api/show payload (GGUF metadata) for llama3.2:3b.
OLLAMA_SHOW = {
    "details": {
        "family": "llama",
        "parameter_size": "3.2B",
        "quantization_level": "Q4_K_M",
    },
    "model_info": {
        "general.architecture": "llama",
        "llama.block_count": 28,
        "llama.attention.head_count": 24,
        "llama.attention.head_count_kv": 8,
        "llama.embedding_length": 3072,
    },
}


class TestParamSize:
    def test_billions(self):
        assert parse_param_size("3.2B") == 3.2

    def test_millions(self):
        assert parse_param_size("494.03M") == pytest.approx(0.49403)

    def test_none_and_garbage(self):
        assert parse_param_size(None) is None
        assert parse_param_size("unknown") is None


class TestHFParser:
    def test_qwen_head_dim_null_computed(self):
        spec = spec_from_hf("Qwen/Qwen2.5-1.5B-Instruct", QWEN_CONFIG, QWEN_PARAMS_B)
        assert spec.n_layers == 28
        assert spec.n_kv_heads == 2  # GQA
        assert spec.d_head == 128  # hidden 1536 / 12 heads, since head_dim was null
        assert spec.vocab_size == 151936
        assert spec.params_b == pytest.approx(1.5437, abs=1e-3)
        assert spec.family == "qwen2.5"
        assert spec.source == "hf"

    def test_mha_when_kv_heads_absent(self):
        cfg = {**QWEN_CONFIG, "num_key_value_heads": None}
        spec = spec_from_hf("x/y", cfg, 1.0)
        assert spec.n_kv_heads == cfg["num_attention_heads"]  # MHA: kv == heads

    def test_missing_params_raises(self):
        with pytest.raises(ResolverError, match="safetensors"):
            spec_from_hf("x/y", QWEN_CONFIG, None)


class TestOllamaParser:
    def test_gguf_metadata(self):
        spec = spec_from_ollama_show("llama3.2:3b", OLLAMA_SHOW)
        assert spec.n_layers == 28
        assert spec.n_kv_heads == 8
        assert spec.d_head == 128  # embedding 3072 / 24 heads
        assert spec.params_b == 3.2
        assert spec.native_quant == "Q4_K_M"
        assert spec.source == SOURCE_OLLAMA

    def test_key_length_preferred_over_computed(self):
        payload = {
            **OLLAMA_SHOW,
            "model_info": {**OLLAMA_SHOW["model_info"], "llama.attention.key_length": 96},
        }
        assert spec_from_ollama_show("llama3.2:3b", payload).d_head == 96

    def test_missing_fields_raise(self):
        with pytest.raises(ResolverError, match="missing required fields"):
            spec_from_ollama_show("x", {"details": {}, "model_info": {}})


class TestOverrides:
    def test_full_overrides(self):
        spec = spec_from_overrides(
            "mystery-7b",
            {"params_b": 7.0, "n_layers": 32, "n_kv_heads": 8, "d_head": 128},
        )
        assert spec is not None
        assert spec.params_b == 7.0
        assert spec.source == SOURCE_MANUAL

    def test_partial_overrides_return_none(self):
        assert spec_from_overrides("x", {"params_b": 7.0, "n_layers": 32}) is None


class TestModelSpec:
    def test_from_registry_exact(self):
        spec = ModelSpec.from_registry("llama3.2-3b")
        assert spec.params_b == 3.21
        assert spec.n_layers == 28
        assert spec.source == SOURCE_REGISTRY

    def test_weight_gb(self):
        spec = ModelSpec.from_registry("llama3.2-3b")
        assert spec.weight_gb("FP16") == pytest.approx(3.21 * 16 / 8)
        assert spec.weight_gb("Q4_K_M") < spec.weight_gb("FP16")

    def test_roundtrip_dict(self):
        spec = ModelSpec.from_registry("qwen2.5-1.5b")
        assert ModelSpec.from_dict(spec.to_dict()) == spec


class TestResolveSpec:
    def test_registry_passthrough(self):
        assert resolve_spec("llama3.2-3b").source == SOURCE_REGISTRY

    def test_manual_overrides_win(self):
        spec = resolve_spec(
            "anything",
            overrides={"params_b": 13.0, "n_layers": 40, "n_kv_heads": 8, "d_head": 128},
        )
        assert spec.params_b == 13.0
        assert spec.source == SOURCE_MANUAL

    def test_offline_family_approximation(self):
        # No network: an Ollama-style tag in a known family approximates the registry.
        spec = resolve_spec("llama3.2:1b", allow_network=False, use_cache=False)
        assert spec.source == SOURCE_REGISTRY_APPROX
        assert spec.params_b == pytest.approx(1.24)

    def test_unresolvable_raises(self):
        with pytest.raises(ResolverError, match="could not resolve"):
            resolve_spec("totally-unknown-xyz", allow_network=False, use_cache=False)

    def test_cache_roundtrip(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CHIMERAFORGE_CACHE", str(tmp_path))
        spec = spec_from_ollama_show("llama3.2:3b", OLLAMA_SHOW)
        from chimeraforge.planner import resolver

        resolver._cache_store("llama3.2:3b", spec)
        assert resolver._cache_load("llama3.2:3b") == spec


class TestRouting:
    """Routing decisions (HF vs Ollama vs approx) with fetchers monkeypatched."""

    def test_slashed_repo_routes_to_hf_not_ollama(self, monkeypatch):
        from chimeraforge.planner import resolver

        monkeypatch.setattr(resolver, "fetch_hf", lambda r, t=None: (QWEN_CONFIG, QWEN_PARAMS_B))

        def _boom(*a, **k):
            raise AssertionError("ollama must not be called for a slashed HF repo")

        monkeypatch.setattr(resolver, "fetch_ollama_show", _boom)
        spec = resolver.resolve_spec("Qwen/Qwen2.5-1.5B-Instruct", use_cache=False)
        assert spec.source == "hf"

    def test_colon_tag_routes_to_ollama(self, monkeypatch):
        from chimeraforge.planner import resolver

        monkeypatch.setattr(resolver, "fetch_ollama_show", lambda tag, url: OLLAMA_SHOW)
        spec = resolver.resolve_spec("qwen3:14b", ollama_url="http://x", use_cache=False)
        assert spec.source == SOURCE_OLLAMA

    def test_ollama_failure_falls_back_to_approx(self, monkeypatch):
        from chimeraforge.planner import resolver

        def _fail(*a, **k):
            raise ResolverError("ollama down")

        monkeypatch.setattr(resolver, "fetch_ollama_show", _fail)
        # Known family -> approximates even though the live fetch failed.
        spec = resolver.resolve_spec("llama3.2:3b", ollama_url="http://x", use_cache=False)
        assert spec.source == SOURCE_REGISTRY_APPROX
        assert spec.registry_alias == "llama3.2-3b"
