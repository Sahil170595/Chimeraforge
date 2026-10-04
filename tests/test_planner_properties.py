"""Generated boundary checks for memory, units, and benchmark statistics."""

from __future__ import annotations

import math
from dataclasses import asdict

import pytest
from hypothesis import given, settings, strategies as st

from chimeraforge.bench.metrics import summarize
from chimeraforge.planner.models import CostModel, LatencyModel, VRAMModel

settings.register_profile("ci", max_examples=80, derandomize=True, deadline=None)
settings.load_profile("ci")

positive = st.floats(min_value=0.01, max_value=10000, allow_nan=False, allow_infinity=False)
architectures = st.fixed_dictionaries(
    {
        "n_layers": st.integers(1, 128),
        "n_kv_heads": st.integers(1, 64),
        "d_head": st.sampled_from([32, 64, 128, 256]),
    }
)


@given(architectures, st.integers(1, 131072), st.integers(1, 64), st.sampled_from([0.5, 1, 2]))
def test_dense_kv_bytes_match_independent_integer_accounting(arch, context, batch, byte_width):
    actual = VRAMModel.kv_cache_gb(arch, context, batch, byte_width)
    elements = 2 * arch["n_layers"] * arch["n_kv_heads"] * arch["d_head"] * context * batch
    assert actual == pytest.approx(elements * byte_width / 1073741824)


@given(architectures, st.integers(1, 32768), st.integers(1, 16), st.integers(1, 16))
def test_cache_memory_scales_with_context_and_concurrency(arch, context, batch, factor):
    baseline = VRAMModel.kv_cache_gb(arch, context, batch)
    assert VRAMModel.kv_cache_gb(arch, context * factor, batch) == pytest.approx(baseline * factor)
    assert VRAMModel.kv_cache_gb(arch, context, batch * factor) == pytest.approx(baseline * factor)


@given(positive, positive, st.integers(1, 64))
def test_per_token_hardware_cost_is_replica_invariant(rate, throughput, replicas):
    cost = CostModel()
    baseline = cost.predict_cost_per_1m(throughput, rate)
    assert cost.predict_cost_per_1m(throughput * replicas, rate * replicas) == pytest.approx(
        baseline
    )
    # Independent dimensional check: charge for exactly one million tokens.
    assert baseline == pytest.approx(rate * (1000000 / throughput) / 3600)


@given(positive)
def test_monthly_cost_accounts_for_all_720_hours(rate):
    assert CostModel().predict_monthly(rate) == pytest.approx(rate * 720)


@given(st.integers(1, 131072), st.integers(1, 32768))
def test_prefill_chunks_cover_prompt_without_an_empty_chunk(tokens, budget):
    chunks = LatencyModel.prefill_chunks(tokens, budget)
    assert (chunks - 1) * budget < tokens <= chunks * budget


@given(
    st.lists(st.floats(-1e6, 1e6, allow_nan=False, allow_infinity=False), min_size=1, max_size=80)
)
def test_percentile_order_and_permutation_invariance(values):
    stats = summarize(values)
    assert stats.min <= stats.p50 <= stats.p95 <= stats.p99 <= stats.max
    independent_mean = math.fsum(values) / len(values)
    assert stats.mean == pytest.approx(independent_mean)
    if len(values) > 1:
        independent_variance = math.fsum((v - independent_mean) ** 2 for v in values) / (
            len(values) - 1
        )
        assert stats.stddev == pytest.approx(math.sqrt(independent_variance))
    assert asdict(summarize(list(reversed(values)))) == pytest.approx(asdict(stats))


@given(st.lists(st.integers(-100000, 100000), min_size=2, max_size=80), st.integers(-1000, 1000))
def test_statistics_translate_without_changing_sample_dispersion(values, shift):
    original, translated = summarize(values), summarize([v + shift for v in values])
    for field in ("mean", "p50", "p95", "p99", "min", "max"):
        assert getattr(translated, field) == pytest.approx(getattr(original, field) + shift)
    assert translated.stddev == pytest.approx(original.stddev)


@given(architectures, st.integers(1, 32768), positive, st.integers(1, 8))
def test_concurrency_ceiling_is_maximal_under_the_memory_budget(arch, context, params, tp):
    model = VRAMModel(overhead_factor=1.10, act_coeff=0)
    hardware_gib, utilisation = 24, 0.9
    count = model.max_concurrent_seqs(
        params, "FP16", arch, context, hardware_gib, utilisation, tp=tp
    )

    def footprint(batch):
        return model.predict("manual", "FP16", context, batch, params, arch, tp=tp)

    if count:
        assert footprint(count) <= hardware_gib * utilisation + 1e-10
    assert footprint(count + 1) > hardware_gib * utilisation
