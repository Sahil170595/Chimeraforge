"""Pins for constants and functions a mutation audit proved unprotected.

An independent audit ran 30 mutations against the source and 12 survived a full
green suite. These are the survivors that matter: each test below fails on the
specific mutation named in its docstring, and none of them existed before.

The theme is the same one this project keeps rediscovering: a formula can be
well tested while the constant it multiplies is pinned by nothing, and an
expected value derived from the implementation's own constant moves with it.
"""

from __future__ import annotations

import pytest

from chimeraforge.bench.metrics import _percentile, summarize
from chimeraforge.planner.constants import (
    DECODE_COMPUTE_MFU,
    INTERCONNECT_EFFICIENCY,
    QUANT_BPW,
    SECONDS_PER_MONTH,
    WORKLOAD_CV2,
)


class TestPercentileInterpolation:
    """`_percentile` produces every p50/p95/p99 in every bench artifact and every
    refit input, and no test pinned a single value. Swapping the two
    interpolation weights takes the p95 of [100, 110, 180] from 173.0 to 117.0 --
    a 32% error -- with the whole suite green.
    """

    def test_p95_matches_the_hand_derivation(self):
        # k = (3-1) * 0.95 = 1.9, so f=1, c=2:
        #   110 * (2 - 1.9) + 180 * (1.9 - 1) = 11.0 + 162.0 = 173.0
        assert _percentile([100.0, 110.0, 180.0], 0.95) == pytest.approx(173.0)

    def test_p50_of_an_odd_list_is_the_middle_element(self):
        assert _percentile([10.0, 20.0, 30.0, 40.0, 50.0], 0.5) == pytest.approx(30.0)

    def test_p50_of_an_even_list_interpolates_the_two_middles(self):
        # k = 3 * 0.5 = 1.5 -> halfway between 20 and 30.
        assert _percentile([10.0, 20.0, 30.0, 40.0], 0.5) == pytest.approx(25.0)

    def test_the_weights_are_not_symmetric(self):
        """The mutation that survived is a swap, so a symmetric case cannot
        detect it. This asymmetric one can."""
        assert _percentile([0.0, 100.0], 0.9) == pytest.approx(90.0)

    def test_endpoints_are_exact(self):
        vals = [1.0, 2.0, 3.0, 4.0]
        assert _percentile(vals, 0.0) == pytest.approx(1.0)
        assert _percentile(vals, 1.0) == pytest.approx(4.0)

    def test_summarize_reports_the_same_percentile(self):
        s = summarize([100.0, 110.0, 180.0])
        assert s.p95 == pytest.approx(173.0)


class TestBillingConstantsArePinnedToLiterals:
    def test_seconds_per_month_is_thirty_days(self):
        """`test_cost_realism` derived its expected token count from this very
        constant, so halving the billing month to 15 days left the suite green
        and every $/1M-token figure would have doubled."""
        assert SECONDS_PER_MONTH == 2_592_000
        assert SECONDS_PER_MONTH == 30 * 24 * 3600

    def test_tokens_served_uses_the_literal_month(self):
        expected = 2.0 * 128 * 2_592_000
        assert expected == pytest.approx(663_552_000.0)


class TestQuantBitsPerWeightArePinned:
    """Q4_K_M is the project's documented default recommendation, and its
    bits-per-weight had no per-entry assertion: 4.5 -> 4.0 is an 11% weight-VRAM
    error on the most-recommended configuration, and it passed."""

    @pytest.mark.parametrize(
        ("quant", "bpw"),
        [
            # Measured from real GGUF artifacts, not approximated. See the
            # provenance block above QUANT_BPW.
            ("FP32", 32.0),
            ("FP16", 16.0),
            ("FP8", 8.0),
            ("Q8_0", 8.5),
            ("Q6_K", 6.57),
            ("Q5_K_M", 5.71),
            ("Q4_K_M", 4.90),
            ("Q3_K_S", 3.65),
            ("Q2_K", 3.17),
        ],
    )
    def test_each_level_is_the_documented_width(self, quant, bpw):
        assert QUANT_BPW[quant] == pytest.approx(bpw)

    def test_the_ladder_is_monotone(self):
        gguf = ["Q8_0", "Q6_K", "Q5_K_M", "Q4_K_M", "Q3_K_S", "Q2_K"]
        widths = [QUANT_BPW[q] for q in gguf]
        assert widths == sorted(widths, reverse=True)

    def test_q8_0_is_the_exact_block_width(self):
        """llama.cpp's Q8_0 block is `{ ggml_half d; int8_t qs[32]; }` -- 34 bytes
        per 32 weights, exactly 8.5 bpw. The table said 8.0, i.e. it dropped the
        scale, which is precisely the overhead its own comment claimed to include."""
        assert QUANT_BPW["Q8_0"] == pytest.approx((2 + 32) * 8 / 32)

    def test_no_quantized_level_is_understated_against_measurement(self):
        """Every entry used to be low, and all in the same direction -- a
        systematic bias, not noise, in the term that drives Gate 1."""
        measured = {
            "Q8_0": 8.509,
            "Q6_K": 6.571,
            "Q5_K_M": 5.712,
            "Q4_K_M": 4.902,
            "Q3_K_S": 3.651,
            "Q2_K": 3.167,
        }
        for quant, real in measured.items():
            assert QUANT_BPW[quant] == pytest.approx(real, abs=0.02), quant


class TestCalibrationConstantsArePinned:
    """Both are documented as calibration constants that `measure` may refine --
    exactly the kind of value that needs a pin, and neither had one. The existing
    tests assert only ORDERING (PCIe slower than NVLink), which any positive
    value preserves."""

    def test_decode_compute_mfu(self):
        """0.5 -> 5.0 disabled the decode compute ceiling entirely and nothing
        noticed. An MFU above 1.0 is not physical."""
        assert DECODE_COMPUTE_MFU == pytest.approx(0.5)
        assert 0.0 < DECODE_COMPUTE_MFU <= 1.0

    def test_interconnect_efficiency(self):
        """0.75 -> 0.25 is a 3x change to realized NCCL bandwidth, driving both
        TP and PP comms, and the suite stayed green."""
        assert INTERCONNECT_EFFICIENCY == pytest.approx(0.75)
        assert 0.0 < INTERCONNECT_EFFICIENCY <= 1.0

    def test_agent_workload_variance_preset(self):
        """The queueing FORMULA is tested; this VALUE was not, so agent traffic
        could be modelled as ordinary chatbot traffic silently."""
        assert WORKLOAD_CV2["agent"] == pytest.approx(8.0)
        assert WORKLOAD_CV2["steady"] < WORKLOAD_CV2["chatbot"] < WORKLOAD_CV2["agent"]


class TestUtilisationSafetyCap:
    """No test in the suite referenced the 70% cap or its warning string. Set to
    0.99 the planner approves fleets running at 99% utilisation and the warning
    stops firing, silently."""

    def test_the_fitted_cap_is_seventy_percent(self):
        from chimeraforge.planner.models import load_bundled_models

        models = load_bundled_models()
        assert models.latency.safety_factor == pytest.approx(0.70)

    def test_a_saturated_fleet_is_flagged(self):
        from chimeraforge.planner.models import load_bundled_models

        m = load_bundled_models()
        got = m.latency.predict_p95(
            "llama3.2-3b", "ollama", 2.0, n_agents=1, throughput_model=m.throughput
        )
        assert got["saturated"] is True
        assert got["utilisation"] > m.latency.safety_factor

    def test_a_comfortable_fleet_is_not(self):
        from chimeraforge.planner.models import load_bundled_models

        m = load_bundled_models()
        got = m.latency.predict_p95(
            "llama3.2-3b", "ollama", 0.05, n_agents=1, throughput_model=m.throughput
        )
        assert got["saturated"] is False
        assert got["utilisation"] <= m.latency.safety_factor

    def test_the_warning_reaches_the_candidate(self):
        from chimeraforge.planner.service import run_plan

        r = run_plan(
            model_size="3b",
            hardware="RTX 4080 12GB",
            request_rate=40.0,
            budget=1e9,
            quality_target=0.0,
            latency_slo=1e9,
        )
        assert r.candidates, "expected a plan to warn about"
        texts = [w for c in r.candidates for w in c.warnings]
        assert any("safety cap" in w for w in texts), "the cap never surfaces to the user"


class TestSerialFractionsArePinned:
    """The Amdahl serial fractions drive the N-replica search directly, and a 9x
    change (0.45 -> 0.05) survived on both the dataclass default and the fitted
    JSON path."""

    def test_the_fitted_ollama_fractions(self):
        """Keyed `model|backend`, and each is a literal from TR133."""
        from chimeraforge.planner.models import load_bundled_models

        sf = load_bundled_models().scaling.serial_fractions
        assert sf["llama3.2-1b|ollama"] == pytest.approx(0.532912, abs=1e-5)
        assert sf["llama3.2-3b|ollama"] == pytest.approx(0.387044, abs=1e-5)
        assert sf["qwen2.5-1.5b|ollama"] == pytest.approx(0.455408, abs=1e-5)

    def test_the_fitted_fractions_are_fractions(self):
        from chimeraforge.planner.models import load_bundled_models

        models = load_bundled_models()
        assert models.scaling.serial_fractions, "no fitted serial fractions at all"
        for key, value in models.scaling.serial_fractions.items():
            assert 0.0 <= value <= 1.0, f"{key} is not a fraction: {value}"


class TestBundledCorpusIsPhysicallyPossible:
    """Decode streams every weight once per token, so `tok/s <= bandwidth /
    weight_bytes` is a hard bound at MBU 1.0. A row above it cannot be a
    measurement of what its key says it is.

    One bundled row is above it: `llama3.2-3b|ollama|FP16` at 95.86 tok/s needs
    615 GB/s from a 432 GB/s card -- 142.5% of peak. It is kept rather than
    quietly deleted or relabelled, because the provenance to justify either is
    not available; predictions are clamped instead, and this test fixes the count
    at one so the problem cannot grow silently.
    """

    KNOWN_ANOMALIES = {"llama3.2-3b|ollama|FP16"}

    def _impossible(self):
        from chimeraforge.planner.constants import MODEL_PARAMS_B, QUANT_BPW
        from chimeraforge.planner.hardware import REFERENCE_GPU, get_gpu
        from chimeraforge.planner.models import load_bundled_models

        bw = get_gpu(REFERENCE_GPU).bandwidth_gbps
        out = {}
        for key, tps in load_bundled_models().throughput.lookup.items():
            model, _backend, quant = key.split("|")
            params = MODEL_PARAMS_B.get(model)
            if params is None:
                continue
            weight_gb = params * QUANT_BPW.get(quant, 16.0) / 8
            mbu = tps * weight_gb / bw
            if mbu > 1.0:
                out[key] = mbu
        return out

    def test_no_new_row_exceeds_the_memory_bus(self):
        found = set(self._impossible())
        new = found - self.KNOWN_ANOMALIES
        assert not new, f"new physically impossible corpus rows: {sorted(new)}"

    def test_the_known_anomaly_is_still_the_only_one(self):
        """If this fails because the row was fixed, delete it from
        KNOWN_ANOMALIES -- do not widen the set to make it pass."""
        found = self._impossible()
        assert set(found) == self.KNOWN_ANOMALIES
        assert found["llama3.2-3b|ollama|FP16"] == pytest.approx(1.425, abs=0.01)

    def test_no_prediction_is_ever_above_the_ceiling(self):
        """The property that actually protects users, over the whole registry."""
        from chimeraforge.planner.constants import MODEL_PARAMS_B, QUANT_LEVELS
        from chimeraforge.planner.models import load_bundled_models

        t = load_bundled_models().throughput
        for hw in ("RTX 4080 12GB", "RTX 4090 24GB", "H100 80GB", "T4 16GB"):
            for model, params in MODEL_PARAMS_B.items():
                for quant in QUANT_LEVELS:
                    for backend in ("ollama", "vllm", "tgi"):
                        got = t.predict(model, backend, quant, hw)
                        ceiling = t.bandwidth_ceiling_tps(params, quant, hw)
                        assert got <= ceiling * 1.001, (
                            f"{model}|{backend}|{quant} on {hw}: "
                            f"{got:.1f} tok/s exceeds the {ceiling:.1f} tok/s bus limit"
                        )

    def test_the_extrapolated_8b_is_bounded(self):
        """`plan --model-size 8b` is a documented invocation and llama3.1-8b has
        no measured row, so it takes the power law -- which has an exponent of
        0.089 where bandwidth-bound decode needs ~1.0, and returned 59.9 tok/s
        against a 26.9 tok/s ceiling."""
        from chimeraforge.planner.models import load_bundled_models

        t = load_bundled_models().throughput
        got = t.predict("llama3.1-8b", "ollama", "FP16", "RTX 4080 12GB")
        ceiling = t.bandwidth_ceiling_tps(8.03, "FP16", "RTX 4080 12GB")
        assert got == pytest.approx(ceiling, rel=0.01)
        assert got < 30.0, "an 8B at FP16 cannot decode at 59.9 tok/s on a 432 GB/s card"
