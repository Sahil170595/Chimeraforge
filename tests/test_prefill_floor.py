"""TTFT's memory-bound floor, and chunked prefill.

P8.3. Two corrections to prefill, both derivations rather than fits.

The floor first. `predict_ttft_ms` was `2 * params * prompt_tokens /
(fp16_tflops * MFU)` with nothing under it, so TTFT was linear in prompt length
all the way to zero. An 8B on an RTX 4090 predicted **0.242 ms for a one-token
prompt** -- a forward pass that has to stream 16 GB of weights, completing in 242
microseconds. Prefill is not purely compute-bound: the weights get read whatever
the prompt length, and that read time is a floor.

This matters more than it looks, because the two features that make TTFT look
best are exactly the ones that push the model into the regime where it was wrong:
`--prefix-cache-hit-rate` (90% of a 4k prompt leaves ~410 uncached tokens) and
short agent prompts.

Chunked prefill second, and it is the sharper finding: vLLM V1 enables it **by
default** (`vllm/config/scheduler.py`, `enable_chunked_prefill: bool = True`), so
the planner was modelling a serving configuration that no longer ships.

The overhead is derived from the stated mechanism -- split a prefill into N
chunks and the first chunk's KV is loaded N-1 times, the second's N-2 -- which is
arithmetic over `ceil(prompt / budget)`. Sarathi-Serve's two published endpoints
are used ONLY as a ceiling to clamp against. Fitting a smooth multiplier through
two points and calling it physics is the mistake the multi-LoRA rank multiplier
already had to guard against.
"""

from __future__ import annotations

import pytest

from chimeraforge.planner.constants import (
    CHUNK_OVERHEAD_CAP,
    FLOPS_PER_PARAM_PER_TOKEN,
    MBU_DEFAULT,
    PREFILL_MFU,
    QUANT_BPW,
)
from chimeraforge.planner.hardware import GPU_DB
from chimeraforge.planner.models import LatencyModel

# The model behind the documented `plan --model-size 8b`.
PARAMS_8B = 8.0
ARCH_8B = {"n_layers": 32, "n_kv_heads": 8, "d_head": 128}


def compute_only_ms(params_b: float, prompt_tokens: int, gpu: str) -> float:
    """The pre-P8.3 formula, kept here so the tests state what changed."""
    tflops = GPU_DB[gpu].fp16_tflops
    flops = FLOPS_PER_PARAM_PER_TOKEN * params_b * 1e9 * prompt_tokens
    return flops / (tflops * 1e12 * PREFILL_MFU) * 1000.0


class TestTheFloorExists:
    @pytest.mark.parametrize("gpu", sorted(GPU_DB))
    @pytest.mark.parametrize("prompt", [1, 2, 16, 64, 128, 512, 4096, 32768])
    def test_ttft_is_never_below_the_weight_read_time(self, gpu, prompt):
        """The property, over every GPU in the database and down to a one-token
        prompt. A forward pass cannot finish before it has read the weights."""
        floor = LatencyModel.prefill_floor_ms(PARAMS_8B, "FP16", gpu)
        ttft = LatencyModel.predict_ttft_ms(PARAMS_8B, prompt, gpu)
        if floor == 0.0:
            return  # unknown bandwidth: no floor is claimed
        assert ttft >= floor * (1 - 1e-9), f"{gpu} @ {prompt} tok: {ttft:.3f} < floor {floor:.3f}"

    def test_the_one_token_case_that_motivated_this(self):
        # 0.242 ms to stream 16 GB. The floor is nearly two orders of magnitude up.
        assert compute_only_ms(PARAMS_8B, 1, "RTX 4090 24GB") == pytest.approx(0.242, abs=0.001)
        assert LatencyModel.predict_ttft_ms(PARAMS_8B, 1, "RTX 4090 24GB") > 15.0

    def test_the_floor_is_the_weight_bytes_over_effective_bandwidth(self):
        gpu = "RTX 4090 24GB"
        weight_gb = PARAMS_8B * QUANT_BPW["FP16"] / 8
        expected = weight_gb / (GPU_DB[gpu].bandwidth_gbps * MBU_DEFAULT) * 1000.0
        assert LatencyModel.prefill_floor_ms(PARAMS_8B, "FP16", gpu) == pytest.approx(expected)

    def test_it_is_a_floor_and_not_a_replacement(self):
        """Long prompts are genuinely compute-bound; the floor must not touch them.

        MBU is calibrated on one datapoint, so it may bound a prediction but never
        become one."""
        gpu = "RTX 4090 24GB"
        long_prompt = 32768
        assert LatencyModel.predict_ttft_ms(PARAMS_8B, long_prompt, gpu) == pytest.approx(
            compute_only_ms(PARAMS_8B, long_prompt, gpu)
        )

    def test_the_floor_scales_with_quantization(self):
        # A Q4 model streams a quarter of the bytes, so its floor is a quarter.
        gpu = "RTX 4090 24GB"
        fp16 = LatencyModel.prefill_floor_ms(PARAMS_8B, "FP16", gpu)
        q4 = LatencyModel.prefill_floor_ms(PARAMS_8B, "Q4_K_M", gpu)
        assert q4 == pytest.approx(fp16 * QUANT_BPW["Q4_K_M"] / QUANT_BPW["FP16"])

    def test_an_unknown_gpu_claims_no_floor(self):
        # Falling back to the reference card's bandwidth would be a silent default.
        assert LatencyModel.prefill_floor_ms(PARAMS_8B, "FP16", "RTX 9999 imaginary") == 0.0
        assert LatencyModel.prefill_floor_ms(PARAMS_8B, "FP16", None) == 0.0

    def test_ttft_stays_zero_when_compute_is_unknown(self):
        # The caller omits the prefill term rather than being handed a floor with
        # no prediction to bound.
        assert LatencyModel.predict_ttft_ms(PARAMS_8B, 512, None) == 0.0


class TestCrossovers:
    """Below the crossover the old model was optimistic, and unboundedly so as
    prompts shrink. Re-derived from the CURRENT constants, not transcribed: 0.30.4
    changed both MBU_DEFAULT and the reference card's TFLOPS, so the figures in the
    roadmap (computed at MBU 0.65) no longer hold."""

    @pytest.mark.parametrize(
        "gpu,crossover", [("RTX 4090 24GB", 78), ("L4 24GB", 192), ("H100 80GB", 140)]
    )
    def test_the_crossover_is_where_compute_overtakes_the_floor(self, gpu, crossover):
        floor = LatencyModel.prefill_floor_ms(PARAMS_8B, "FP16", gpu)
        # Just below: the floor binds. Just above: compute does.
        assert LatencyModel.predict_ttft_ms(PARAMS_8B, crossover - 5, gpu) == pytest.approx(floor)
        assert LatencyModel.predict_ttft_ms(PARAMS_8B, crossover + 5, gpu) > floor

    def test_a_prefix_cache_hit_can_push_a_plan_under_the_crossover(self):
        """The feature that makes TTFT look best is the one that reaches the regime
        the floor exists for.

        A 95% hit rate on a 2k prompt leaves ~102 uncached tokens, under the L4's
        192-token crossover, so the old model reported 33.7 ms for a prefill that
        cannot beat 63.5 ms. (A 90% hit on 4k leaves 409 tokens, which is *above*
        that crossover -- the regime is reached by short prompts, not by any
        cache hit, and the test says which.)"""
        uncached = int(2048 * 0.05)
        floor = LatencyModel.prefill_floor_ms(PARAMS_8B, "FP16", "L4 24GB")
        assert compute_only_ms(PARAMS_8B, uncached, "L4 24GB") < floor
        assert LatencyModel.predict_ttft_ms(PARAMS_8B, uncached, "L4 24GB") == pytest.approx(floor)
        # And the case that does NOT reach it stays a compute prediction.
        assert LatencyModel.predict_ttft_ms(PARAMS_8B, 409, "L4 24GB") > floor


class TestChunkedPrefillIsOffByDefault:
    """`max_num_batched_tokens >= prompt_tokens` must reproduce the unchunked
    number byte-for-byte, so the default path is provably unchanged."""

    def test_no_budget_means_one_chunk(self):
        assert LatencyModel.prefill_chunks(8192, None) == 1
        assert LatencyModel.prefill_chunks(8192, 0) == 1

    def test_a_budget_at_or_above_the_prompt_is_one_chunk(self):
        assert LatencyModel.prefill_chunks(2048, 2048) == 1
        assert LatencyModel.prefill_chunks(2048, 4096) == 1

    @pytest.mark.parametrize("prompt", [1, 64, 512, 2048])
    def test_a_budget_that_does_not_split_changes_nothing(self, prompt):
        gpu = "RTX 4090 24GB"
        unchunked = LatencyModel.predict_ttft_ms(PARAMS_8B, prompt, gpu, arch=ARCH_8B)
        chunked = LatencyModel.predict_ttft_ms(
            PARAMS_8B, prompt, gpu, arch=ARCH_8B, max_num_batched_tokens=prompt
        )
        assert chunked == unchunked

    def test_no_reread_without_a_split(self):
        assert LatencyModel.chunk_kv_reread_ms(512, 2048, ARCH_8B, "RTX 4090 24GB") == 0.0


class TestChunkOverheadIsDerivedThenClamped:
    def test_chunk_count_is_the_ceiling_division(self):
        assert LatencyModel.prefill_chunks(8192, 2048) == 4
        assert LatencyModel.prefill_chunks(8193, 2048) == 5  # a remainder is a chunk

    def test_the_reread_is_quadratic_in_chunk_count(self):
        """N*(N-1)/2 extra chunk-loads. Doubling the chunk count nearly quadruples
        the re-read, which is the shape the mechanism implies -- not a curve fit."""
        gpu = "H100 80GB"
        four = LatencyModel.chunk_kv_reread_ms(8192, 2048, ARCH_8B, gpu)
        eight = LatencyModel.chunk_kv_reread_ms(16384, 2048, ARCH_8B, gpu)
        # 4 chunks -> 6 extra loads; 8 chunks -> 28. Same chunk size, so the ratio
        # of times is the ratio of extra loads.
        assert eight / four == pytest.approx(28 / 6, rel=1e-6)

    def test_chunking_never_makes_prefill_faster(self):
        gpu = "RTX 4090 24GB"
        unchunked = LatencyModel.predict_ttft_ms(PARAMS_8B, 8192, gpu, arch=ARCH_8B)
        chunked = LatencyModel.predict_ttft_ms(
            PARAMS_8B, 8192, gpu, arch=ARCH_8B, max_num_batched_tokens=512
        )
        assert chunked >= unchunked

    @pytest.mark.parametrize("budget", [128, 256, 512, 1024, 2048])
    @pytest.mark.parametrize("gpu", ["RTX 4090 24GB", "H100 80GB", "L4 24GB"])
    def test_overhead_never_exceeds_the_published_ceiling(self, budget, gpu):
        """25% is the only overhead figure anyone has measured, at the smallest
        budget they measured. The derived quadratic is clamped there rather than
        being allowed to run past it."""
        unchunked = LatencyModel.predict_ttft_ms(PARAMS_8B, 16384, gpu, arch=ARCH_8B)
        chunked = LatencyModel.predict_ttft_ms(
            PARAMS_8B, 16384, gpu, arch=ARCH_8B, max_num_batched_tokens=budget
        )
        assert chunked <= unchunked * (1 + CHUNK_OVERHEAD_CAP) * (1 + 1e-9)

    def test_a_bigger_budget_costs_less_than_a_smaller_one(self):
        # The direction the published endpoints assert: ~25% at 512, negligible at
        # 2048. The derivation has to agree with that ordering at minimum.
        gpu = "RTX 4090 24GB"
        small = LatencyModel.predict_ttft_ms(
            PARAMS_8B, 16384, gpu, arch=ARCH_8B, max_num_batched_tokens=512
        )
        large = LatencyModel.predict_ttft_ms(
            PARAMS_8B, 16384, gpu, arch=ARCH_8B, max_num_batched_tokens=2048
        )
        assert small > large

    def test_no_arch_means_no_reread_term(self):
        # Without a KV shape there is nothing to re-read, and inventing one would
        # be exactly the fabricated constant this item avoids. The weight re-reads
        # still count, so chunking is not free.
        gpu = "RTX 4090 24GB"
        assert LatencyModel.chunk_kv_reread_ms(16384, 512, None, gpu) == 0.0
        assert LatencyModel.predict_ttft_ms(
            PARAMS_8B, 16384, gpu, max_num_batched_tokens=512
        ) >= LatencyModel.predict_ttft_ms(PARAMS_8B, 16384, gpu)


class TestPlanSurface:
    def test_the_flag_reaches_the_engine_and_moves_ttft(self):
        from chimeraforge.planner.service import run_plan

        kw = dict(
            model_size="8b",
            hardware="RTX 4090 24GB",
            budget=1e9,
            quality_target=0.0,
            latency_slo=1e9,
            prompt_tokens=16384,
            context_length=32768,
            allow_network=False,
        )
        plain = run_plan(**kw).candidates[0]
        chunked = run_plan(**kw, max_num_batched_tokens=512).candidates[0]
        assert chunked.ttft_ms > plain.ttft_ms

    def test_chunking_is_disclosed_not_silent(self):
        from chimeraforge.planner.service import run_plan

        c = run_plan(
            model_size="8b",
            hardware="RTX 4090 24GB",
            budget=1e9,
            quality_target=0.0,
            latency_slo=1e9,
            prompt_tokens=16384,
            context_length=32768,
            max_num_batched_tokens=512,
            allow_network=False,
        ).candidates[0]
        assert any("chunked prefill" in w for w in c.warnings)
        assert any("ESTIMATED" in w for w in c.warnings)

    def test_a_misaligned_budget_warns_and_is_not_modelled(self):
        """Tile quantization is sharp -- 257 measured ~32% slower than 256 -- and
        deliberately not modelled, so it has to be named."""
        from chimeraforge.planner.service import run_plan

        c = run_plan(
            model_size="8b",
            hardware="RTX 4090 24GB",
            budget=1e9,
            quality_target=0.0,
            latency_slo=1e9,
            prompt_tokens=16384,
            context_length=32768,
            max_num_batched_tokens=257,
            allow_network=False,
        ).candidates[0]
        assert any("multiple of 256" in w for w in c.warnings)

    def test_an_uncalibrated_budget_says_so(self):
        from chimeraforge.planner.service import run_plan

        c = run_plan(
            model_size="8b",
            hardware="RTX 4090 24GB",
            budget=1e9,
            quality_target=0.0,
            latency_slo=1e9,
            prompt_tokens=16384,
            context_length=32768,
            max_num_batched_tokens=8192,
            allow_network=False,
        ).candidates[0]
        assert any("not calibrated" in w for w in c.warnings)

    def test_the_floor_is_disclosed_when_it_binds(self):
        from chimeraforge.planner.service import run_plan

        c = run_plan(
            model_size="8b",
            hardware="L4 24GB",
            budget=1e9,
            quality_target=0.0,
            latency_slo=1e9,
            prompt_tokens=16,
            allow_network=False,
        ).candidates[0]
        assert any("memory-bound FLOOR" in w for w in c.warnings)

    def test_the_launch_export_emits_the_budget(self):
        from chimeraforge.planner.engine import Candidate
        from chimeraforge.planner.launch import build_launch_command

        c = Candidate(
            model="llama3.1-8b",
            quant="FP16",
            backend="vllm",
            n_agents=1,
            vram_gb=18.0,
            quality=0.6,
            quality_tier="acceptable",
            throughput_tps=50.0,
            total_throughput_tps=50.0,
            eta=1.0,
            p95_latency_ms=500.0,
            utilisation=0.5,
            monthly_cost=100.0,
            cost_per_1m_tok=0.1,
            safety_refusal=None,
            rtsi_risk="UNKNOWN",
            warnings=[],
        )
        cmd = build_launch_command(c, None, context_length=8192, max_num_batched_tokens=2048)
        assert "--max-num-batched-tokens 2048" in cmd.command
        # Off by default: the flag must not appear when the plan did not chunk.
        assert (
            "--max-num-batched-tokens"
            not in build_launch_command(c, None, context_length=8192).command
        )
