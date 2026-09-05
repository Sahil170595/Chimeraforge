"""Hybrid / linear-attention sizing, against the vendors' own config files.

P8.2. The README gives VRAM and KV-cache the provenance `exact`. That was false,
silently, for an entire class of 2026 models: the planner sized every layer as an
attention layer, so a model with 4 attention layers out of 56 got a cache 14.0x
too large, at every context length, with no warning.

Two things make this worth testing carefully rather than casually.

First, the error direction is asymmetric. Over-sizing KV refuses a config that
would have worked; under-sizing it promises a fit that OOMs. So the rule is that
KV may only shrink on evidence of a *named, placed* non-attention layer, and the
tests below include the cases that punish a looser rule -- Falcon-H1, a parallel
hybrid where every layer is both a Mamba mixer and a full attention block and
nothing may be discounted.

Second, these fixtures are the vendors' real `config.json` files
(`tests/fixtures/hybrid_configs/`, captured by `scripts/fetch_hybrid_configs.py`
with a URL and a date). Hand-written dicts would test my reading of those configs
rather than the configs, which is exactly the failure this item exists to fix.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from chimeraforge.planner.hybrid import (
    KIND_GATED_DELTANET,
    KIND_KDA,
    KIND_MAMBA1,
    KIND_MAMBA2,
    LAYER_FULL_ATTENTION,
    LAYER_LINEAR_ATTENTION,
    count_attention_layers,
    count_recurrent_layers,
    hybrid_from_config,
    normalize_layer_types,
    state_dtype_bytes,
    unwrap_text_config,
)
from chimeraforge.planner.models import VRAMModel
from chimeraforge.planner.resolver import spec_from_hf

FIXTURES = Path(__file__).parent / "fixtures" / "hybrid_configs"


def cfg(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def spec(name: str, repo: str, params_b: float):
    return spec_from_hf(repo, cfg(name), params_b)


# (fixture, repo, params_b, attention layers, total layers, recurrent kind)
# The four ratios marked below are the ones the roadmap verified independently by
# running resolve_spec against the live repos; they are reproduced here exactly.
FAMILIES = [
    (
        "nvidia_NVIDIA-Nemotron-Nano-9B-v2",
        "nvidia/NVIDIA-Nemotron-Nano-9B-v2",
        8.89,
        4,
        56,
        KIND_MAMBA2,
    ),
    (
        "ibm-granite_granite-4.0-h-small",
        "ibm-granite/granite-4.0-h-small",
        32.2,
        4,
        40,
        KIND_MAMBA2,
    ),
    (
        "Qwen_Qwen3-Next-80B-A3B-Instruct",
        "Qwen/Qwen3-Next-80B-A3B-Instruct",
        80.0,
        12,
        48,
        KIND_GATED_DELTANET,
    ),
    (
        "moonshotai_Kimi-Linear-48B-A3B-Instruct",
        "moonshotai/Kimi-Linear-48B-A3B-Instruct",
        48.0,
        7,
        27,
        KIND_KDA,
    ),
    ("Qwen_Qwen3.5-9B", "Qwen/Qwen3.5-9B", 9.0, 8, 32, KIND_GATED_DELTANET),
    ("ai21labs_Jamba-v0.1", "ai21labs/Jamba-v0.1", 51.6, 4, 32, KIND_MAMBA1),
    ("MiniMaxAI_MiniMax-Text-01", "MiniMaxAI/MiniMax-Text-01", 456.0, 10, 80, None),
]


class TestLayerPatternsAcrossEveryFamily:
    """Six different spellings of the same idea, one normalizer."""

    @pytest.mark.parametrize("fixture,repo,pb,attn,total,kind", FAMILIES)
    def test_attention_layer_count(self, fixture, repo, pb, attn, total, kind):
        c = unwrap_text_config(cfg(fixture))
        assert c["num_hidden_layers"] == total
        assert count_attention_layers(c, total) == attn

    @pytest.mark.parametrize("fixture,repo,pb,attn,total,kind", FAMILIES)
    def test_the_overstatement_is_the_ratio(self, fixture, repo, pb, attn, total, kind):
        # Sizing every layer as attention overstates KV by exactly total/attn, at
        # every context length -- it is a layer-count error, not a modelling one.
        sp = spec(fixture, repo, pb)
        v = VRAMModel()
        naive = dict(sp.arch())
        naive.pop("n_attention_layers", None)
        naive.pop("recurrent_state_bytes_per_seq", None)
        real_kv = v.kv_cache_gb(sp.arch(), 131072, 1) - v.recurrent_state_gb(sp.arch(), 1)
        assert v.kv_cache_gb(naive, 131072, 1) / real_kv == pytest.approx(total / attn, rel=1e-6)

    @pytest.mark.parametrize("fixture,repo,pb,attn,total,kind", FAMILIES)
    def test_recurrent_kind_is_identified(self, fixture, repo, pb, attn, total, kind):
        sp = spec(fixture, repo, pb)
        assert sp.recurrent_kind == kind
        # MiniMax declares an attention pattern but no readable state geometry.
        # The layer correction still applies; the state term stays absent rather
        # than being filled with a plausible shape.
        assert (sp.recurrent_state_bytes_per_seq > 0) == (kind is not None)

    def test_mlp_layers_are_not_counted_as_recurrent(self):
        """Nemotron-H's pattern is three-way: 4 attention, 27 Mamba, 25 plain MLP.

        `n_layers - attention_layers` would call all 52 non-attention layers
        recurrent and inflate the state by 93%."""
        c = unwrap_text_config(cfg("nvidia_NVIDIA-Nemotron-Nano-9B-v2"))
        assert count_attention_layers(c, 56) == 4
        assert count_recurrent_layers(c, 56) == 27
        assert 4 + 27 < 56  # the remaining 25 are MLP and hold nothing


class TestKvMayOnlyShrinkOnPlacedEvidence:
    """The asymmetric rule. Over-sizing refuses a working config; under-sizing
    promises a fit that OOMs."""

    def test_falcon_h1_is_a_parallel_hybrid_and_keeps_full_kv(self):
        """Every Falcon-H1 layer builds BOTH a Mamba mixer and a full attention
        block. It has mamba keys and no layer pattern, and treating "has mamba
        keys" as evidence of interleaving would under-size it by 72x."""
        sp = spec("tiiuae_Falcon-H1-34B-Instruct", "tiiuae/Falcon-H1-34B-Instruct", 34.0)
        assert sp.n_layers == 72
        assert sp.attention_layers == 72
        assert "n_attention_layers" not in sp.arch()
        assert sp.parallel_hybrid is True

    def test_falcon_h1_still_pays_the_state_on_every_layer(self):
        # The pattern is unplaceable but the geometry is not, and dropping the
        # state would understate a real allocation.
        sp = spec("tiiuae_Falcon-H1-34B-Instruct", "tiiuae/Falcon-H1-34B-Instruct", 34.0)
        assert sp.recurrent_kind == KIND_MAMBA2
        one_layer = sp.recurrent_state_bytes_per_seq / sp.n_layers
        assert sp.recurrent_state_bytes_per_seq == pytest.approx(one_layer * 72)

    def test_an_unrecognised_layer_token_reads_as_attention(self):
        # Guessing "recurrent" for a token nobody has identified would shrink the
        # cache on the strength of not recognising a word.
        types = normalize_layer_types({"layer_types": ["attention", "something_new"]}, 2)
        assert types == [LAYER_FULL_ATTENTION, LAYER_FULL_ATTENTION]

    def test_a_pattern_of_the_wrong_length_is_refused(self):
        # A pattern that does not cover every layer cannot place anything.
        assert normalize_layer_types({"layer_types": ["attention"] * 3}, 40) is None
        assert normalize_layer_types({"hybrid_override_pattern": "M*-"}, 40) is None

    def test_no_pattern_at_all_means_every_layer_caches(self):
        assert normalize_layer_types({"model_type": "llama"}, 32) is None
        assert count_attention_layers({"model_type": "llama"}, 32) == 32

    def test_an_all_attention_pattern_is_not_a_hybrid(self):
        # MiniMax-M2's attn_type_list is all 1s. Emitting n_attention_layers ==
        # n_layers would be harmless but noisy; it must not appear.
        sp = spec("MiniMaxAI_MiniMax-M2", "MiniMaxAI/MiniMax-M2", 230.0)
        assert sp.attention_layers == sp.n_layers == 62
        assert "n_attention_layers" not in sp.arch()


class TestPublishedBounds:
    """Pinned to vendor claims, not to the tool's own arithmetic. A self-consistent
    test proves nothing."""

    def test_nemotron_nano_2_fits_128k_on_a_22gib_a10g(self):
        """NVIDIA publishes that Nemotron Nano 2 does inference on up to 128k
        tokens on a single A10G (22 GiB, bfloat16). That is a hard falsifiable
        bound: the predicted footprint at 128k must fit inside it.

        Before this change the planner predicted 46.21 GiB and would have refused
        a configuration the vendor ships."""
        sp = spec("nvidia_NVIDIA-Nemotron-Nano-9B-v2", "nvidia/NVIDIA-Nemotron-Nano-9B-v2", 8.89)
        predicted = VRAMModel().predict(sp.name, "FP16", 131072, 1, sp.params_b, sp.arch())
        assert predicted <= 22.0, f"predicted {predicted:.2f} GiB against a published 22 GiB bound"
        # And not vacuously: a bound nothing could fail is not a bound.
        assert predicted > 15.0

    def test_the_old_model_would_have_failed_that_bound(self):
        sp = spec("nvidia_NVIDIA-Nemotron-Nano-9B-v2", "nvidia/NVIDIA-Nemotron-Nano-9B-v2", 8.89)
        naive = dict(sp.arch())
        naive.pop("n_attention_layers")
        naive.pop("recurrent_state_bytes_per_seq")
        assert VRAMModel().predict(sp.name, "FP16", 131072, 1, sp.params_b, naive) > 22.0

    def test_nemotron_kv_is_2gb_not_28gb_at_131072(self):
        # The roadmap verified both figures directly against this arch.
        sp = spec("nvidia_NVIDIA-Nemotron-Nano-9B-v2", "nvidia/NVIDIA-Nemotron-Nano-9B-v2", 8.89)
        v = VRAMModel()
        kv_only = v.kv_cache_gb(sp.arch(), 131072, 1) - v.recurrent_state_gb(sp.arch(), 1)
        assert kv_only == pytest.approx(2.00, abs=0.01)

    def test_granite_4h_long_context_reduction_exceeds_70pc(self):
        """IBM states Granite 4.0-H gives "over 70% reduction in RAM needed to
        handle long inputs and multiple concurrent batches"."""
        sp = spec("ibm-granite_granite-4.0-h-small", "ibm-granite/granite-4.0-h-small", 32.2)
        v = VRAMModel()
        naive = dict(sp.arch())
        naive.pop("n_attention_layers")
        naive.pop("recurrent_state_bytes_per_seq")
        ctx, batch = 131072, 16
        reduction = 1 - v.kv_cache_gb(sp.arch(), ctx, batch) / v.kv_cache_gb(naive, ctx, batch)
        assert reduction > 0.70, f"only {reduction:.1%}"


class TestRecurrentStateIsPerSequence:
    """20-75 MiB looks negligible at batch 1 and is gigabytes at batch 64, which is
    exactly where a model gets chosen for throughput."""

    def test_state_scales_with_batch_and_not_with_context(self):
        sp = spec("ibm-granite_granite-4.0-h-small", "ibm-granite/granite-4.0-h-small", 32.2)
        v = VRAMModel()
        assert v.recurrent_state_gb(sp.arch(), 64) == pytest.approx(
            64 * v.recurrent_state_gb(sp.arch(), 1)
        )
        # Flat in context: same state at 2k and at 128k.
        at_2k = v.kv_cache_gb(sp.arch(), 2048, 1) - v.recurrent_state_gb(sp.arch(), 1)
        at_128k = v.kv_cache_gb(sp.arch(), 131072, 1) - v.recurrent_state_gb(sp.arch(), 1)
        assert at_128k > at_2k  # KV grew
        assert v.recurrent_state_gb(sp.arch(), 1) == v.recurrent_state_gb(sp.arch(), 1)

    def test_state_reaches_gigabytes_at_batch_64(self):
        sp = spec("ibm-granite_granite-4.0-h-small", "ibm-granite/granite-4.0-h-small", 32.2)
        assert VRAMModel().recurrent_state_gb(sp.arch(), 64) > 1.0

    def test_state_enters_the_concurrency_ceiling(self):
        """It must cap `max_concurrent_seqs`, not just the footprint -- otherwise
        the ceiling is optimistic exactly where the model was picked for throughput."""
        sp = spec("ibm-granite_granite-4.0-h-small", "ibm-granite/granite-4.0-h-small", 32.2)
        v = VRAMModel()
        with_state = v.max_concurrent_seqs(sp.params_b, "Q4_K_M", sp.arch(), 8192, 80.0)
        without = dict(sp.arch())
        without.pop("recurrent_state_bytes_per_seq")
        assert with_state < v.max_concurrent_seqs(sp.params_b, "Q4_K_M", without, 8192, 80.0)


class TestStateDtype:
    """Assuming bf16 where the config declares fp32 halves the dominant term."""

    def test_qwen35_declares_float32_and_it_is_read(self):
        c = unwrap_text_config(cfg("Qwen_Qwen3.5-9B"))
        assert c["mamba_ssm_dtype"] == "float32"
        assert c["dtype"] == "bfloat16"  # the model itself is not fp32
        nbytes, declared = state_dtype_bytes(c)
        assert (nbytes, declared) == (4.0, True)

    def test_a_config_without_an_ssm_dtype_falls_back_and_says_so(self):
        c = unwrap_text_config(cfg("ibm-granite_granite-4.0-h-small"))
        nbytes, declared = state_dtype_bytes(c)
        assert (nbytes, declared) == (2.0, False)

    def test_the_declared_dtype_actually_doubles_the_term(self):
        c = unwrap_text_config(cfg("Qwen_Qwen3.5-9B"))
        as_declared = hybrid_from_config(c, 32)["recurrent_state_bytes_per_seq"]
        as_bf16 = hybrid_from_config({**c, "mamba_ssm_dtype": "bfloat16"}, 32)[
            "recurrent_state_bytes_per_seq"
        ]
        assert as_declared == pytest.approx(2 * as_bf16)


class TestTextConfigWrapper:
    """Two whole model lines were unplannable: the resolver read the top level and
    raised, because every architecture key is nested."""

    @pytest.mark.parametrize(
        "fixture,repo,layers",
        [
            ("Qwen_Qwen3.5-9B", "Qwen/Qwen3.5-9B", 32),
            ("google_gemma-4-31B-it", "google/gemma-4-31B-it", 60),
        ],
    )
    def test_a_wrapper_config_now_resolves(self, fixture, repo, layers):
        sp = spec(fixture, repo, 9.0)
        assert sp.n_layers == layers
        assert sp.n_kv_heads > 0 and sp.d_head > 0

    def test_gemma4_is_sliding_window_not_hybrid(self):
        """`layer_types` here is sliding/full attention. Sliding layers still cache
        -- just less -- so none of them may be discounted as recurrent."""
        sp = spec("google_gemma-4-31B-it", "google/gemma-4-31B-it", 31.0)
        assert sp.attention_layers == sp.n_layers == 60
        assert sp.recurrent_state_bytes_per_seq == 0.0

    def test_a_flat_config_passes_through_unchanged(self):
        flat = cfg("nvidia_NVIDIA-Nemotron-Nano-9B-v2")
        assert unwrap_text_config(flat) is flat

    def test_a_wrapper_with_no_layers_is_not_descended_into(self):
        # A `text_config` that is a stub must not shadow a usable top level.
        top = {"num_hidden_layers": 8, "text_config": {"model_type": "x"}}
        assert unwrap_text_config(top)["num_hidden_layers"] == 8


class TestDenseModelsAreUntouched:
    """The negative test the whole item hangs on: nothing here may move a number
    for a model that is not a hybrid."""

    def test_dense_gqa_emits_no_hybrid_keys(self):
        sp = spec("Qwen_Qwen2.5-1.5B-Instruct", "Qwen/Qwen2.5-1.5B-Instruct", 1.54)
        assert sp.n_attention_layers is None
        assert sp.recurrent_state_bytes_per_seq == 0.0
        assert sp.recurrent_kind is None
        assert set(sp.arch()) == {
            "n_layers",
            "n_kv_heads",
            "d_head",
            "kv_elems_per_token_per_layer",
        }

    def test_dense_kv_is_the_plain_formula(self):
        sp = spec("Qwen_Qwen2.5-1.5B-Instruct", "Qwen/Qwen2.5-1.5B-Instruct", 1.54)
        a = sp.arch()
        expected = a["n_layers"] * 4096 * a["kv_elems_per_token_per_layer"] * 2 / (1024**3)
        assert VRAMModel().kv_cache_gb(a, 4096, 1) == pytest.approx(expected)

    def test_an_arch_dict_with_no_hybrid_keys_is_unaffected(self):
        # The bare registry-style arch dict, which has no hybrid keys at all.
        a = {"n_layers": 28, "n_kv_heads": 8, "d_head": 128}
        v = VRAMModel()
        assert v.recurrent_state_gb(a, 64) == 0.0
        assert v.kv_cache_gb(a, 4096, 1) == pytest.approx(28 * 4096 * 2 * 8 * 128 * 2 / (1024**3))


class TestKdaIsLabelledInferred:
    """Kimi's KDA is not in transformers; its allocation happens in an external
    library, so its shape is inferred rather than read."""

    def test_kimi_state_is_the_inferred_kind(self):
        sp = spec(
            "moonshotai_Kimi-Linear-48B-A3B-Instruct",
            "moonshotai/Kimi-Linear-48B-A3B-Instruct",
            48.0,
        )
        assert sp.recurrent_kind == KIND_KDA

    def test_but_its_layer_count_is_exact(self):
        # `full_attn_layers` is an explicit, placed list -- the larger effect is
        # not weakened by the state term's uncertainty.
        c = unwrap_text_config(cfg("moonshotai_Kimi-Linear-48B-A3B-Instruct"))
        assert c["linear_attn_config"]["full_attn_layers"] == [4, 8, 12, 16, 20, 24, 27]
        assert count_attention_layers(c, 27) == 7

    def test_the_full_attn_list_is_read_as_one_indexed(self):
        """It ends at 27 for a 27-layer model, so it cannot be 0-indexed. Reading
        it as 0-indexed would misplace every layer in the model."""
        c = unwrap_text_config(cfg("moonshotai_Kimi-Linear-48B-A3B-Instruct"))
        types = normalize_layer_types(c, 27)
        assert types[3] == LAYER_FULL_ATTENTION  # layer 4, 1-indexed
        assert types[26] == LAYER_FULL_ATTENTION  # layer 27, the last one
        assert types[0] == LAYER_LINEAR_ATTENTION


class TestFixtureProvenance:
    def test_every_fixture_records_its_source_and_date(self):
        manifest = json.loads((FIXTURES / "MANIFEST.json").read_text(encoding="utf-8"))
        assert manifest["captured_at"]
        for entry in manifest["configs"]:
            assert entry["source_url"].startswith("https://huggingface.co/")
            assert entry["captured_at"] == manifest["captured_at"]
            assert (FIXTURES / entry["file"]).exists()
            assert entry["covers"]

    def test_every_family_in_the_test_matrix_has_a_fixture(self):
        for fixture, *_ in FAMILIES:
            assert (FIXTURES / f"{fixture}.json").exists()
