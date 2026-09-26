"""Numerical accuracy gates -- make the predictive models falsifiable.

These pin predictions to ground truth (the bundled measured corpus, the roofline
calibration anchor, and first-principles arithmetic) within stated tolerance
bands. If a model change silently shifts a number, one of these fails. The point
(per the cold review) is that without numerical assertions the models are
unfalsifiable; this file is the falsifiability gate.
"""

from __future__ import annotations

import pytest

from chimeraforge.planner.models import LatencyModel, VRAMModel

REF_GPU = "RTX 4080 12GB"  # the rig the bundled corpus was measured on (ratio 1.0)


class TestThroughputReproducesMeasured:
    """On the reference GPU, predict() reproduces the measured lookup exactly."""

    @pytest.mark.parametrize(
        "model,expected",
        # llama3.2-3b is deliberately absent: its bundled ollama FP16 row (95.86
        # tok/s) implies 142.5% of the reference card's 432 GB/s, which no decode
        # loop can reach, so the prediction is clamped to the bandwidth ceiling and
        # cannot reproduce the row. See TestBundledCorpusIsPhysicallyPossible.
        [("llama3.2-1b", 146.33), ("qwen2.5-1.5b", 139.61)],
    )
    def test_ollama_fp16_lookup(self, bundled_models, model, expected):
        tps = bundled_models.throughput.predict(model, "ollama", "FP16", REF_GPU)
        assert tps == pytest.approx(expected, rel=0.01)


class TestRooflineCalibration:
    """The MBU=0.65 anchor: roofline reproduces the llama3.2-1b ollama datapoint."""

    def test_anchor_point_within_band(self, bundled_models):
        # 0.65 * 556 GB/s / (1.24B * 2 bytes) = 145.7 tok/s vs measured 146.33.
        tps = bundled_models.throughput.roofline_tps(1.24, "FP16", REF_GPU)
        assert tps == pytest.approx(146.33, rel=0.03)

    def test_roofline_scales_with_bandwidth(self, bundled_models):
        # 4090 (1008 GB/s) vs the reference 4080 Laptop (432) -> ~2.33x for the
        # same model. The reference was carried as 556 GB/s, which is neither the
        # laptop part (192-bit, 432) nor the desktop one (717); correcting it
        # moved every cross-GPU ratio by +29%.
        #
        # Read from GPU_DB rather than hardcoded, so this pins the RELATIONSHIP --
        # roofline is linear in bandwidth -- instead of re-encoding two constants
        # that would then move together with the code and assert nothing.
        from chimeraforge.planner.hardware import GPU_DB

        ref_bw = GPU_DB["RTX 4080 12GB"].bandwidth_gbps
        target_bw = GPU_DB["RTX 4090 24GB"].bandwidth_gbps
        t4080 = bundled_models.throughput.roofline_tps(7.0, "FP16", "RTX 4080 12GB")
        t4090 = bundled_models.throughput.roofline_tps(7.0, "FP16", "RTX 4090 24GB")
        assert t4090 / t4080 == pytest.approx(target_bw / ref_bw, rel=0.02)
        assert ref_bw == 432.0, "the reference rig is the RTX 4080 Laptop: 192-bit, 432 GB/s"


class TestVRAMAccuracy:
    def test_formula_composes_weight_kv_activation(self, bundled_models):
        # predict() must equal weight*overhead + KV + activations using the model's
        # own (fitted) coefficients -- validates the formula without hardcoding a
        # value that legitimately drifts on refit.
        m = bundled_models.vram
        arch = {"n_layers": 28, "n_kv_heads": 8, "d_head": 128}  # llama3.2-3b
        # GiB, matching kv_cache_gb and GPUSpec.vram_gb. The weight term used to
        # be decimal GB while the KV term was binary, so this sum mixed units and
        # overstated the total by 7.37%.
        from chimeraforge.planner.constants import GB_TO_GIB

        weight = 3.21 * 16 / 8 * GB_TO_GIB * m.overhead_factor
        kv = m.kv_cache_gb(arch, 2048, 1)
        act = m.act_coeff * arch["n_layers"] * (2048 / 1024)  # linear in ctx (flash attn)
        assert m.predict("llama3.2-3b", "FP16", 2048) == pytest.approx(weight + kv + act, rel=1e-3)

    def test_long_context_activation_stays_physical(self, bundled_models):
        # Regression: activation memory must be O(ctx), not O(ctx^2). A quadratic
        # term blew up to ~130 GB at 32k for a 3B model and spuriously failed the
        # VRAM gate. Linear keeps it bounded well under the weight footprint.
        v = bundled_models.vram.predict("llama3.2-3b", "FP16", 32768)
        assert v < 20.0, f"32k-ctx VRAM {v:.1f} GB is unphysically large -- activation not linear?"

    def test_absolute_band(self, bundled_models):
        # A 3.21B FP16 model at 2048 ctx must land in a physically sane VRAM band.
        assert 6.5 < bundled_models.vram.predict("llama3.2-3b", "FP16", 2048) < 8.5

    def test_kv_cache_byte_exact(self):
        # 2(KV) * 28L * 2048 ctx * 8 kv-heads * 128 d * 2 bytes = 234,881,024 B.
        kv = VRAMModel.kv_cache_gb({"n_layers": 28, "n_kv_heads": 8, "d_head": 128}, 2048, 1)
        assert kv == pytest.approx(234_881_024 / 1024**3, rel=1e-6)


class TestTTFTAccuracy:
    def test_prefill_compute_formula(self):
        # 2 * 7e9 * 512 / (165.2e12 * 0.4) * 1000 = 108.5 ms on a 4090.
        ttft = LatencyModel.predict_ttft_ms(7.0, 512, "RTX 4090 24GB")
        assert ttft == pytest.approx(108.5, rel=0.01)


class TestBatchedThroughputInvariants:
    """Physical invariants of the continuous-batching curve."""

    KV = 0.05  # GB per sequence (small relative to weights)

    def test_b1_equals_single_stream(self, bundled_models):
        assert bundled_models.throughput.batched_decode_tps(100.0, self.KV, 1, REF_GPU) == 100.0

    def test_monotonic_increasing_then_saturates(self, bundled_models):
        tp = bundled_models.throughput
        a = tp.batched_decode_tps(100.0, self.KV, 2, REF_GPU)
        b = tp.batched_decode_tps(100.0, self.KV, 8, REF_GPU)
        c = tp.batched_decode_tps(100.0, self.KV, 64, REF_GPU)
        assert 100.0 < a < b < c  # aggregate rises with batch
        # saturates below the KV-bandwidth ceiling bw*MBU/kv.
        ceiling = 556.0 * 0.65 / self.KV
        assert c < ceiling

    def test_per_request_rate_drops_with_batch(self, bundled_models):
        # The throughput<->latency tradeoff: per-sequence rate falls as batch rises.
        tp = bundled_models.throughput
        agg2 = tp.batched_decode_tps(100.0, self.KV, 2, REF_GPU)
        agg16 = tp.batched_decode_tps(100.0, self.KV, 16, REF_GPU)
        assert agg16 / 16 < agg2 / 2 <= 100.0


class TestThirdPartyAuditDoesNotWiden:
    """P8.5 regression gates: the published third-party error bands, pinned.

    Values are the headline rows of corpora/scorecard.json as first published
    (2026-09-25): fully specified third-party cells, roofline-estimate class.
    They are typed here rather than read from the scorecard so that regenerating
    the scorecard cannot loosen the gate -- widening one means editing this file,
    in a diff someone reviews. Tolerance absorbs rounding, not regressions.
    """

    TOL = 0.005
    # (provenance class, metric): (n, median abs error, GMFE, worst abs error)
    PUBLISHED = {
        ("roofline-estimate", "throughput_tps"): (15, 0.3588, 1.629, 2.0634),
        ("roofline-estimate", "ttft_ms"): (14, 1.3538, 2.6795, 1.8389),
    }

    @pytest.fixture(scope="class")
    def live_rows(self):
        import importlib.util
        import pathlib

        path = (
            pathlib.Path(__file__).resolve().parents[1] / "scripts" / "build_validation_corpus.py"
        )
        spec = importlib.util.spec_from_file_location("build_validation_corpus", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        rows = mod.combined(mod.run_audit()["audits"]).rows
        return {(r.provenance_class, r.metric): r for r in rows if r.evidence}

    @pytest.mark.parametrize("key", sorted(PUBLISHED))
    def test_error_band_has_not_widened(self, live_rows, key):
        n, med, gmfe, worst = self.PUBLISHED[key]
        row = live_rows[key]
        assert row.n == n, "the audited cell set changed; re-register, do not re-score"
        assert row.median_abs <= med + self.TOL
        assert row.gmfe <= gmfe + self.TOL
        assert abs(row.worst_error) <= worst + self.TOL
