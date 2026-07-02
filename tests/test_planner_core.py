"""Tests for planner constants, hardware DB, and serialization round-trips."""

from __future__ import annotations

import json

import pytest

from chimeraforge.planner.constants import (
    MODEL_ARCH,
    MODEL_PARAMS_B,
    QUANT_BPW,
    QUANT_LEVELS,
)
from chimeraforge.planner.hardware import (
    GPU_DB,
    REFERENCE_GPU,
    bandwidth_ratio,
    get_gpu,
)
from chimeraforge.planner.models import load_models


# -- Constants & Registry ---------------------------------------------


class TestConstants:
    def test_quant_levels_ordered_descending(self):
        bpws = [QUANT_BPW[q] for q in QUANT_LEVELS]
        assert bpws == sorted(bpws, reverse=True)

    def test_all_quants_have_bpw(self):
        for q in QUANT_LEVELS:
            assert q in QUANT_BPW

    def test_model_params_and_arch_consistent(self):
        assert set(MODEL_PARAMS_B.keys()) == set(MODEL_ARCH.keys())

    def test_model_arch_keys(self):
        for model, arch in MODEL_ARCH.items():
            assert "n_layers" in arch
            assert "n_kv_heads" in arch
            assert "d_head" in arch
            assert arch["n_layers"] > 0
            assert arch["n_kv_heads"] > 0
            assert arch["d_head"] > 0


# -- Hardware DB ------------------------------------------------------


class TestHardwareDB:
    def test_reference_gpu_exists(self):
        assert REFERENCE_GPU in GPU_DB

    def test_gpu_spec_fields(self):
        for name, spec in GPU_DB.items():
            assert spec.vram_gb > 0
            assert spec.bandwidth_gbps > 0
            assert spec.cost_per_hour > 0
            assert spec.name == name

    def test_get_gpu_exact(self):
        spec = get_gpu("RTX 4090 24GB")
        assert spec is not None
        assert spec.vram_gb == 24.0

    def test_get_gpu_case_insensitive(self):
        spec = get_gpu("rtx 4090 24gb")
        assert spec is not None
        assert spec.vram_gb == 24.0

    def test_get_gpu_unknown(self):
        assert get_gpu("AMD RX 7900 XTX") is None

    def test_bandwidth_ratio_reference(self):
        assert bandwidth_ratio(REFERENCE_GPU) == pytest.approx(1.0)

    def test_bandwidth_ratio_faster_gpu(self):
        assert bandwidth_ratio("RTX 4090 24GB") > 1.0

    def test_bandwidth_ratio_unknown(self):
        assert bandwidth_ratio("Unknown GPU") == 1.0


# -- Serialization Round-Trip -----------------------------------------


class TestSerialization:
    def test_round_trip(self, bundled_models, tmp_path):
        # Serialize
        data = {
            "vram": bundled_models.vram.to_dict(),
            "throughput": bundled_models.throughput.to_dict(),
            "scaling": bundled_models.scaling.to_dict(),
            "quality": bundled_models.quality.to_dict(),
            "cost": bundled_models.cost.to_dict(),
            "latency": bundled_models.latency.to_dict(),
        }
        path = tmp_path / "models.json"
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

        loaded = load_models(path)

        # VRAM predictions match
        for model in ["llama3.2-1b", "llama3.2-3b"]:
            orig = bundled_models.vram.predict(model, "FP16", 2048)
            back = loaded.vram.predict(model, "FP16", 2048)
            assert orig == pytest.approx(back)

        # Throughput predictions match
        orig_t = bundled_models.throughput.predict("llama3.2-3b", "ollama", "FP16")
        back_t = loaded.throughput.predict("llama3.2-3b", "ollama", "FP16")
        assert orig_t == pytest.approx(back_t)

    def test_json_keys(self, bundled_models, tmp_path):
        data = {
            "vram": bundled_models.vram.to_dict(),
            "throughput": bundled_models.throughput.to_dict(),
            "scaling": bundled_models.scaling.to_dict(),
            "quality": bundled_models.quality.to_dict(),
            "cost": bundled_models.cost.to_dict(),
            "latency": bundled_models.latency.to_dict(),
        }
        assert set(data.keys()) == {"vram", "throughput", "scaling", "quality", "cost", "latency"}

    def test_bundled_models_are_fitted(self, bundled_models):
        assert bundled_models.vram.fitted
        assert bundled_models.throughput.fitted
        assert bundled_models.scaling.fitted
        assert bundled_models.quality.fitted
        assert bundled_models.latency.fitted


# -- Serialization Extended ---------------------------------------------------


class TestSerializationExtended:
    def test_round_trip_all_models(self, bundled_models, tmp_path):
        """All 6 models round-trip correctly."""
        data = {
            "vram": bundled_models.vram.to_dict(),
            "throughput": bundled_models.throughput.to_dict(),
            "scaling": bundled_models.scaling.to_dict(),
            "quality": bundled_models.quality.to_dict(),
            "cost": bundled_models.cost.to_dict(),
            "latency": bundled_models.latency.to_dict(),
        }
        path = tmp_path / "models.json"
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        loaded = load_models(path)

        # Scaling
        for model in ["llama3.2-3b"]:
            for n in [1, 4, 8]:
                orig = bundled_models.scaling.predict_eta(model, "ollama", n)
                back = loaded.scaling.predict_eta(model, "ollama", n)
                assert orig == pytest.approx(back)

        # Quality
        orig_q = bundled_models.quality.predict("llama3.2-3b", "Q4_K_M")
        back_q = loaded.quality.predict("llama3.2-3b", "Q4_K_M")
        assert orig_q == pytest.approx(back_q)

        # Cost
        orig_c = bundled_models.cost.predict_monthly()
        back_c = loaded.cost.predict_monthly()
        assert orig_c == pytest.approx(back_c)

    def test_empty_json_returns_defaults(self, tmp_path):
        path = tmp_path / "empty.json"
        path.write_text("{}", encoding="utf-8")
        loaded = load_models(path)
        # Should not crash, uses defaults
        assert loaded.vram.overhead_factor == 1.10
        assert loaded.vram.fitted is False
