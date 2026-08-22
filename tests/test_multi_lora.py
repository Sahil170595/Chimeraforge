"""Tests for multi-LoRA serving.

This feature has two halves with different epistemic status, and the tests keep
them apart on purpose.

Adapter VRAM is exact arithmetic: LoRA factorises a (d_in x d_out) weight into
A (d_in x r) and B (r x d_out), so it is pinned against the published parameter
count for Llama-2-7B q/v (``524288 * r``) rather than against itself.

The decode cost is not exact. It comes from one vendor sweep on one engine, one
GPU and one model, which published two rank endpoints and not the two intermediate
ranks it tested. So the tests assert the endpoints match the source, that anything
between them is interpolated (never claimed as measured), that it clamps instead of
extrapolating, and that every LoRA plan carries a warning naming the source.
"""

from __future__ import annotations

import pytest

from chimeraforge.planner.constants import (
    LORA_BYTES_PER_PARAM,
    LORA_RANK_THROUGHPUT,
    LORA_SOURCE,
    LORA_TARGETS,
    MAX_LORA_ADAPTERS,
    MAX_LORA_RANK,
)
from chimeraforge.planner.engine import enumerate_candidates
from chimeraforge.planner.launch import build_launch_command
from chimeraforge.planner.models import ThroughputModel, load_bundled_models
from chimeraforge.planner.resolver import ModelSpec

# Llama-2-7B: 32 layers, MHA (32 heads x 128), hidden 4096. The reference case for
# the published q/v parameter formula.
LLAMA2_7B = ModelSpec(
    name="meta-llama/Llama-2-7b-hf",
    params_b=6.74,
    n_layers=32,
    n_kv_heads=32,
    d_head=128,
    hidden_size=4096,
    source="hf",
)
# Llama-3.1-8B: same hidden/layers but GQA (8 KV heads), so k/v are 8x narrower.
LLAMA31_8B = ModelSpec(
    name="meta-llama/Llama-3.1-8B-Instruct",
    params_b=8.03,
    n_layers=32,
    n_kv_heads=8,
    d_head=128,
    hidden_size=4096,
    source="hf",
)


@pytest.fixture(scope="module")
def models():
    return load_bundled_models()


def _plan(models, spec=LLAMA31_8B, **over):
    kw = dict(
        models=models,
        target_models=[spec.name],
        hardware="A100 80GB",
        request_rate=2.0,
        latency_slo=20000,
        quality_target=0.0,
        budget=1e9,
        avg_tokens=128,
        context_length=2048,
        specs={spec.name: spec},
    )
    kw.update(over)
    return enumerate_candidates(**kw)


def _vllm_fp16(cands):
    return next(c for c in cands if c.backend == "vllm" and c.quant == "FP16")


class TestExactGeometry:
    @pytest.mark.parametrize("rank", [1, 8, 16, 32, 64])
    def test_matches_published_llama2_7b_qv_formula(self, rank):
        """Ground truth, not self-consistency: PEFT q/v on Llama-2-7B is documented
        as 524288 * r trainable parameters."""
        assert LLAMA2_7B.lora_params_per_adapter(rank, "qv") == 524_288 * rank

    def test_gqa_narrows_the_v_projection(self):
        # k and v project to n_kv_heads * d_head, so a GQA model's adapter is
        # strictly smaller than the MHA model of the same hidden size.
        assert LLAMA31_8B.lora_params_per_adapter(16, "qv") < LLAMA2_7B.lora_params_per_adapter(
            16, "qv"
        )

    def test_gqa_value_is_exact(self):
        # 32 layers * rank 16 * [(4096+4096) q + (4096+1024) v] = 6,815,744
        assert LLAMA31_8B.lora_params_per_adapter(16, "qv") == 6_815_744

    def test_attn_target_is_larger_than_qv(self):
        qv = LLAMA31_8B.lora_params_per_adapter(16, "qv")
        attn = LLAMA31_8B.lora_params_per_adapter(16, "attn")
        assert attn > qv
        # attn adds k (same width as v) and o (same width as q), so exactly double.
        assert attn == 2 * qv

    def test_params_scale_linearly_in_rank(self):
        a = LLAMA31_8B.lora_params_per_adapter(8)
        b = LLAMA31_8B.lora_params_per_adapter(32)
        assert b == 4 * a

    def test_bytes_are_fp16(self):
        """A hand-computed literal, not the production expression.

        This asserted `p * LORA_BYTES_PER_PARAM / 1e9`, which is literally the
        body of lora_gb_per_adapter -- so mutating the constant 2.0 -> 8.0 left
        the suite green while sizing every adapter as fp64: a 4x error in the
        term that decides whether a multi-LoRA deployment fits the card.
        """
        # 6,815,744 params x 2 bytes = 13,631,488 bytes = 0.013631488 GB.
        assert LLAMA31_8B.lora_params_per_adapter(16) == 6_815_744
        assert LLAMA31_8B.lora_gb_per_adapter(16) == pytest.approx(0.013631488, abs=1e-9)
        assert LORA_BYTES_PER_PARAM == 2.0, "adapters are served in fp16"

    def test_zero_rank_is_zero(self):
        assert LLAMA31_8B.lora_params_per_adapter(0) == 0
        assert LLAMA31_8B.lora_gb_per_adapter(0) == 0.0

    def test_unknown_target_sizes_nothing(self):
        assert LLAMA31_8B.lora_params_per_adapter(16, "mlp") == 0

    def test_target_set_is_only_what_can_be_derived(self):
        # MLP targets need the dense intermediate_size, which ModelSpec does not
        # always carry. Offering them would mean guessing a width.
        assert set(LORA_TARGETS) == {"qv", "attn"}


class TestThroughputMultiplier:
    def test_endpoints_match_the_published_sweep(self):
        lo, hi = min(LORA_RANK_THROUGHPUT), max(LORA_RANK_THROUGHPUT)
        assert ThroughputModel.lora_multiplier(lo) == LORA_RANK_THROUGHPUT[lo]
        assert ThroughputModel.lora_multiplier(hi) == LORA_RANK_THROUGHPUT[hi]

    def test_published_degradation_range_is_what_the_source_says(self):
        # 23.9%-47.0% for vLLM across the tested ranks.
        assert 1 - LORA_RANK_THROUGHPUT[8] == pytest.approx(0.239, abs=0.001)
        assert 1 - LORA_RANK_THROUGHPUT[64] == pytest.approx(0.470, abs=0.001)

    def test_monotone_in_rank(self):
        vals = [ThroughputModel.lora_multiplier(r) for r in (8, 16, 32, 64)]
        assert vals == sorted(vals, reverse=True)

    def test_clamps_instead_of_extrapolating(self):
        """A two-point line run outward invents numbers for ranks nobody measured --
        at rank 512 a linear extrapolation would go negative."""
        lo, hi = min(LORA_RANK_THROUGHPUT), max(LORA_RANK_THROUGHPUT)
        assert ThroughputModel.lora_multiplier(1) == LORA_RANK_THROUGHPUT[lo]
        assert ThroughputModel.lora_multiplier(512) == LORA_RANK_THROUGHPUT[hi]
        assert ThroughputModel.lora_multiplier(512) > 0

    def test_interpolated_ranks_lie_strictly_between(self):
        lo, hi = LORA_RANK_THROUGHPUT[8], LORA_RANK_THROUGHPUT[64]
        for r in (16, 32):
            assert hi < ThroughputModel.lora_multiplier(r) < lo

    def test_midpoint_is_log_spaced(self):
        # Ranks double, so rank 32 sits 2/3 of the way from 8 to 64 in log2.
        lo, hi = LORA_RANK_THROUGHPUT[8], LORA_RANK_THROUGHPUT[64]
        assert ThroughputModel.lora_multiplier(32) == pytest.approx(lo + (2 / 3) * (hi - lo))

    def test_never_speeds_anything_up(self):
        assert all(ThroughputModel.lora_multiplier(r) < 1.0 for r in (1, 8, 16, 32, 64, 128))


class TestEngine:
    def test_adapters_add_vram(self, models):
        base = _vllm_fp16(_plan(models))
        with_lora = _vllm_fp16(_plan(models, lora_adapters=16, lora_rank=32))
        assert with_lora.vram_gb > base.vram_gb
        assert with_lora.lora_gb == pytest.approx(16 * LLAMA31_8B.lora_gb_per_adapter(32), abs=1e-4)

    def test_vram_add_is_linear_in_adapter_count(self, models):
        a = _vllm_fp16(_plan(models, lora_adapters=4, lora_rank=16))
        b = _vllm_fp16(_plan(models, lora_adapters=8, lora_rank=16))
        assert b.lora_gb == pytest.approx(2 * a.lora_gb, rel=1e-6)

    def test_decode_rate_falls_with_rank(self, models):
        rates = [
            _vllm_fp16(_plan(models, lora_adapters=8, lora_rank=r)).throughput_tps
            for r in (8, 16, 32, 64)
        ]
        assert rates == sorted(rates, reverse=True)

    def test_decode_rate_is_flat_in_adapter_count(self, models):
        """The source found throughput near-constant from 2 to 64 adapters, so count
        must not scale the decode rate. Modelling it would be a fit to nothing."""
        a = _vllm_fp16(_plan(models, lora_adapters=2, lora_rank=16))
        b = _vllm_fp16(_plan(models, lora_adapters=32, lora_rank=16))
        assert a.throughput_tps == pytest.approx(b.throughput_tps, rel=1e-9)

    def test_default_off_is_byte_identical(self, models):
        """Every pre-0.27.0 plan must be unchanged: the feature is opt-in."""
        base = _plan(models)
        explicit_zero = _plan(models, lora_adapters=0)
        assert [c.vram_gb for c in base] == [c.vram_gb for c in explicit_zero]
        assert [c.throughput_tps for c in base] == [c.throughput_tps for c in explicit_zero]
        assert all(c.lora_adapters == 0 and c.lora_gb == 0.0 for c in base)

    def test_rank_is_not_recorded_when_no_adapters(self, models):
        # Reporting rank 16 on a plan with no adapters would read as a setting in use.
        assert all(c.lora_rank == 0 for c in _plan(models, lora_adapters=0, lora_rank=16))

    def test_warning_names_the_source_and_its_scope(self, models):
        c = _vllm_fp16(_plan(models, lora_adapters=8, lora_rank=32))
        joined = " ".join(c.warnings)
        assert "ESTIMATED" in joined
        assert LORA_SOURCE in joined
        assert "interpolated" in joined

    def test_warning_says_vram_is_exact(self, models):
        c = _vllm_fp16(_plan(models, lora_adapters=8, lora_rank=32))
        assert any("exact geometry" in w for w in c.warnings)

    def test_warning_declares_the_unmodelled_count_spread(self, models):
        c = _vllm_fp16(_plan(models, lora_adapters=8, lora_rank=32))
        assert any("VRAM only" in w and "not modelled" in w for w in c.warnings)

    def test_spec_without_hidden_size_is_rejected_not_guessed(self, models):
        """Collapsing hidden to the GQA KV width would under-size the adapter, and an
        under-sized adapter claims a fit that is not there."""
        thin = ModelSpec(
            name="x/unknown-shape", params_b=8.0, n_layers=32, n_kv_heads=8, d_head=128, source="hf"
        )
        trace: list = []
        got = _plan(models, spec=thin, lora_adapters=4, trace=trace)
        assert got == []
        assert any("hidden_size" in d for _, _, gate, d in trace if gate == "vram")

    def test_same_spec_plans_fine_without_lora(self, models):
        thin = ModelSpec(
            name="x/unknown-shape", params_b=8.0, n_layers=32, n_kv_heads=8, d_head=128, source="hf"
        )
        assert _plan(models, spec=thin)

    @pytest.mark.parametrize(
        "kwargs,match",
        [
            ({"lora_adapters": -1}, "must be >= 0"),
            ({"lora_adapters": MAX_LORA_ADAPTERS + 1}, "ceiling"),
            ({"lora_adapters": 4, "lora_rank": 0}, "lora_rank"),
            ({"lora_adapters": 4, "lora_rank": MAX_LORA_RANK + 1}, "lora_rank"),
            ({"lora_adapters": 4, "lora_target": "mlp"}, "unknown lora_target"),
        ],
    )
    def test_bad_input_fails_loud(self, models, kwargs, match):
        with pytest.raises(ValueError, match=match):
            _plan(models, **kwargs)

    def test_attn_target_costs_more_vram_than_qv(self, models):
        qv = _vllm_fp16(_plan(models, lora_adapters=8, lora_rank=16, lora_target="qv"))
        attn = _vllm_fp16(_plan(models, lora_adapters=8, lora_rank=16, lora_target="attn"))
        assert attn.lora_gb > qv.lora_gb


class TestLaunchExport:
    def _cand(self, backend, **over):
        from chimeraforge.planner.engine import Candidate

        base = dict(
            model="org/m",
            quant="FP16",
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
            lora_adapters=4,
            lora_rank=32,
        )
        base.update(over)
        return Candidate(**base)

    def test_vllm_flags(self):
        cmd = build_launch_command(self._cand("vllm"), None, context_length=2048).command
        assert "--enable-lora" in cmd
        assert "--max-loras 4" in cmd
        assert "--max-lora-rank 32" in cmd

    def test_sglang_flags(self):
        cmd = build_launch_command(self._cand("sglang"), None, context_length=2048).command
        assert "--lora-paths" in cmd and "--max-loras-per-batch 4" in cmd

    def test_tgi_flags(self):
        cmd = build_launch_command(self._cand("tgi"), None, context_length=2048).command
        assert "--lora-adapters" in cmd

    def test_adapter_path_is_a_placeholder_not_invented(self):
        """The planner has no idea where the adapters live. A command that looks
        runnable and silently serves the wrong adapter is worse than one that
        visibly needs filling in."""
        lc = build_launch_command(self._cand("vllm"), None, context_length=2048)
        assert "<adapter-path>" in lc.command
        assert any("adapter path" in n for n in lc.notes)

    def test_ollama_gets_a_note_not_a_flag(self):
        # llama.cpp merges a LoRA into the base weights; it does not serve adapters
        # per request, so a flag here would be fiction.
        lc = build_launch_command(self._cand("ollama", model="qwen3:8b"), None, context_length=2048)
        assert "lora" not in lc.command.lower()
        assert any("merge the adapter" in n for n in lc.notes)

    def test_no_lora_emits_no_flags(self):
        lc = build_launch_command(
            self._cand("vllm", lora_adapters=0, lora_rank=0), None, context_length=2048
        )
        assert "lora" not in lc.command.lower()
        assert not any("adapter" in n for n in lc.notes)


class TestSurfaces:
    def test_cli_plans_with_adapters(self):
        import json

        from typer.testing import CliRunner

        from chimeraforge.cli import app

        r = CliRunner().invoke(
            app,
            [
                "plan",
                "--model",
                "meta-llama/Llama-3.1-8B-Instruct",
                "--hardware",
                "A100 80GB",
                "--no-network",
                "--params-b",
                "8.03",
                "--n-layers",
                "32",
                "--n-kv-heads",
                "8",
                "--d-head",
                "128",
                "--hidden-size",
                "4096",
                "--budget",
                "1e9",
                "--latency-slo",
                "20000",
                "--lora-adapters",
                "16",
                "--lora-rank",
                "32",
                "--json",
            ],
        )
        assert r.exit_code == 0, r.output
        got = json.loads(r.output[r.output.index("[") : r.output.rindex("]") + 1])
        assert got[0]["lora_adapters"] == 16
        assert got[0]["lora_rank"] == 32
        assert got[0]["lora_gb"] > 0

    def test_mcp_tool_exposes_the_knobs(self):
        import inspect

        from chimeraforge.mcp_server import plan_deployment

        params = inspect.signature(plan_deployment).parameters
        assert {"lora_adapters", "lora_rank", "lora_target"} <= set(params)

    def test_brief_records_adapters_as_derived(self):
        from chimeraforge.planner.brief import PROV_DERIVED, BriefInputs, build_brief
        from chimeraforge.planner.service import run_plan

        r = run_plan(
            models=["meta-llama/Llama-3.1-8B-Instruct"],
            hardware="A100 80GB",
            budget=1e9,
            latency_slo=20000,
            quality_target=0.0,
            allow_network=False,
            lora_adapters=8,
            lora_rank=16,
            overrides={
                "params_b": 8.03,
                "n_layers": 32,
                "n_kv_heads": 8,
                "d_head": 128,
                "hidden_size": 4096,
            },
        )
        assert r.candidates
        b = build_brief(
            inputs=BriefInputs(
                hardware="A100 80GB",
                model="meta-llama/Llama-3.1-8B-Instruct",
                lora_adapters=8,
                lora_rank=16,
            ),
            candidates=r.candidates,
        )
        row = next(m for m in b.metrics if m.label == "LoRA adapters")
        assert row.provenance == PROV_DERIVED
        assert "--lora-adapters 8" in b.inputs.repro_command()
