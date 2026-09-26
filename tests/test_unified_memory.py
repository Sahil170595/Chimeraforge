"""Unified-memory devices (P8.6 item 4): Apple Silicon, Strix Halo, DGX Spark.

The CPU and GPU share one pool, so the tempting reading -- the whole pool is
VRAM -- claims memory the OS and every other app also need. The share the GPU
may use is a required input with no default, the reserve is named, and the plan
says that one bandwidth figure serves both, so decode is an upper bound.

Figures are typed from the vendor pages (Apple Mac spec pages and newsroom, AMD's
Ryzen AI Halo pages, NVIDIA's DGX Spark docs, read 2026-09-26), not read from the
dataset, so a dataset edit has to agree with a reviewed test.
"""

from __future__ import annotations

import json

import pytest

from chimeraforge.planner.hardware import (
    GPU_DB,
    HardwareError,
    apply_unified_fraction,
    match_unified,
    resolve_hardware,
)
from chimeraforge.planner.service import run_plan

# name: (memory configurations sold, bandwidth GB/s)
UNIFIED = {
    "Apple A18 Pro 5-core GPU 8GB": ([8], 60),
    "Apple M4 8-core GPU 24GB": ([16, 24], 120),
    "Apple M4 10-core GPU 32GB": ([16, 24, 32], 120),
    "Apple M5 8-core GPU 16GB": ([16], 153),
    "Apple M5 10-core GPU 32GB": ([16, 24, 32], 153),
    "Apple M6 16GB": ([16], 153),
    "Apple M6 32GB": ([24, 32], 170),
    "Apple M5 Pro 16-core GPU 48GB": ([24, 48], 307),
    "Apple M5 Pro 20-core GPU 64GB": ([24, 48, 64], 307),
    "Apple M5 Max 32-core GPU 36GB": ([36], 460),
    "Apple M5 Max 40-core GPU 128GB": ([48, 64, 128], 614),
    "Apple M5 Ultra 64-core GPU 256GB": ([96, 256], 1200),
    "Apple M5 Ultra 80-core GPU 256GB": ([96, 256], 1200),
    "Ryzen AI Max+ 395 128GB": ([128], 256),
    "DGX Spark 128GB": ([128], 273),
}

KW = dict(model_size="8b", budget=1e9, quality_target=0.0, latency_slo=1e9)
PRICE = {"cost_per_hour": 0.1}


class TestTheDevices:
    @pytest.mark.parametrize("name", sorted(UNIFIED))
    def test_vendor_figures(self, name):
        memory, bandwidth = UNIFIED[name]
        g = GPU_DB[name]
        assert g.unified_memory
        assert g.memory_options_gb == tuple(float(m) for m in memory)
        assert g.vram_gb == float(max(memory))
        assert g.bandwidth_gbps == float(bandwidth)
        assert g.source_url.startswith("https://")

    def test_nothing_unpublished_is_filled_in(self):
        for name in UNIFIED:
            g = GPU_DB[name]
            assert g.fp16_tflops == 0.0, f"{name}: no vendor dense FP16 figure exists"
            assert g.cost_per_hour == 0.0, f"{name}: no per-device vendor price"
            assert not g.fp8_supported

    def test_amd_unlabeled_fp16_headline_is_not_used(self):
        """AMD prints "60 FP16 TFLOPS" with no dense/sparse label."""
        assert GPU_DB["Ryzen AI Max+ 395 128GB"].tflops_basis == "unlabeled-by-vendor"

    def test_apple_power_is_not_a_chip_tdp(self):
        assert all(GPU_DB[n].tdp_watts == 0.0 for n in UNIFIED if n.startswith("Apple"))
        assert GPU_DB["DGX Spark 128GB"].tdp_watts == 140.0  # "GB10 SOC ... TDP is 140W"


class TestTheShareIsAnInput:
    def test_no_default_fraction(self):
        with pytest.raises(HardwareError, match="no default"):
            apply_unified_fraction(GPU_DB["Apple M5 Max 40-core GPU 128GB"], None)

    @pytest.mark.parametrize("bad", [0.0, -0.5, 1.5])
    def test_fraction_is_validated(self, bad):
        with pytest.raises(HardwareError, match=r"\(0, 1\]"):
            apply_unified_fraction(GPU_DB["DGX Spark 128GB"], bad)

    def test_a_fraction_on_a_discrete_card_is_an_error_not_ignored(self):
        with pytest.raises(HardwareError, match="dedicated VRAM"):
            apply_unified_fraction(GPU_DB["RTX 4090 24GB"], 0.5)

    def test_the_plannable_memory_is_the_share(self):
        spec, warnings = apply_unified_fraction(GPU_DB["Apple M5 Max 40-core GPU 128GB"], 0.75)
        assert spec.vram_gb == 96.0
        text = " ".join(warnings)
        assert "32 GB is left to the OS" in text
        assert "upper bound" in text
        assert "48, 64, 128 GB" in text  # the configurations, so the user can correct it


def _plan(hardware, **kw):
    base = dict(KW, hardware=hardware, gpu_overrides=PRICE, unified_memory_fraction=0.75)
    base.update(kw)
    return run_plan(**base)


class TestPlans:
    def test_apple_plans_on_macos_where_vllm_is_cpu_only(self):
        plan = _plan("Apple M5 Max 40-core GPU 128GB")
        assert plan.platform == "macos"
        backends = {c.backend for c in plan.candidates}
        assert "ollama" in backends and "vllm" not in backends
        assert any(t[2] == "platform" and "CPU only" in t[3] for t in plan.trace)

    def test_vram_in_the_plan_is_bounded_by_the_share(self):
        plan = _plan("Apple M5 Max 40-core GPU 128GB")
        assert all(c.vram_gb <= 96.0 for c in plan.candidates)

    def test_the_warnings_travel_with_every_candidate(self):
        plan = _plan("Apple M5 Max 40-core GPU 128GB")
        for c in plan.candidates:
            assert any("left to the OS" in w for w in c.warnings)
            assert any("upper bound" in w for w in c.warnings)

    def test_strix_halo_follows_the_rocm_row(self):
        """vLLM lists Ryzen AI MAX (gfx1151); SGLang and TGI document Instinct only."""
        plan = _plan("Ryzen AI Max+ 395 128GB")
        backends = {c.backend for c in plan.candidates}
        assert "vllm" in backends and "ollama" in backends
        assert not {"sglang", "tgi"} & backends

    def test_dgx_spark_follows_the_cuda_row(self):
        plan = _plan("DGX Spark 128GB")
        assert {c.platform for c in plan.candidates} == {"linux-cuda"}

    def test_apple_on_linux_is_refused(self):
        with pytest.raises(ValueError, match="--platform macos"):
            _plan("Apple M5 Max 40-core GPU 128GB", platform="linux")

    def test_missing_fraction_fails_the_plan(self):
        with pytest.raises(HardwareError, match="unified-memory-fraction"):
            _plan("DGX Spark 128GB", unified_memory_fraction=None)


class TestAuto:
    def test_chip_and_installed_memory_pick_the_variant(self):
        assert match_unified("Apple M5 Max", 64).name == "Apple M5 Max 40-core GPU 128GB"
        assert match_unified("Apple M5 Max", 36).name == "Apple M5 Max 32-core GPU 36GB"
        assert match_unified("Apple M6", 24).name == "Apple M6 32GB"  # 170 GB/s config

    def test_an_unsold_configuration_matches_nothing(self):
        assert match_unified("Apple M5 Max", 40) is None
        assert match_unified("Apple M2", 16) is None

    def test_auto_uses_the_installed_memory_not_the_largest(self, monkeypatch):
        from chimeraforge.doctor import DetectedGPU

        monkeypatch.setattr(
            "chimeraforge.planner.hardware.detect_local_device",
            lambda: DetectedGPU(
                "apple", "Apple M5 Max", 64.0, None, "system_profiler", unified_memory=True
            ),
        )
        spec, warnings = resolve_hardware("auto")
        assert spec.name == "Apple M5 Max 40-core GPU 128GB" and spec.vram_gb == 64.0
        assert any("matched" in w for w in warnings)

    def test_doctor_reports_a_matched_mac_as_plannable(self):
        from chimeraforge.doctor import DetectedGPU, assess

        s = assess(
            DetectedGPU("apple", "Apple M5 Pro", 48.0, None, "system_profiler", unified_memory=True)
        )
        assert s.status == "matched" and "--unified-memory-fraction" in s.detail


class TestEveryPathCarriesTheKnob:
    def test_cli(self):
        from typer.testing import CliRunner

        from chimeraforge.cli import app

        r = CliRunner().invoke(
            app,
            [
                "plan",
                "--model-size",
                "8b",
                "--hardware",
                "DGX Spark 128GB",
                "--unified-memory-fraction",
                "0.5",
                "--gpu-price-per-hour",
                "0.1",
                "--budget",
                "1e9",
                "--quality-target",
                "0",
                "--json",
            ],
        )
        assert r.exit_code == 0, r.output
        assert all(c["vram_gb"] <= 64.0 for c in json.loads(r.output))

    def test_cli_fleet_refuses_the_combination(self):
        from typer.testing import CliRunner

        from chimeraforge.cli import app

        r = CliRunner().invoke(
            app,
            [
                "plan",
                "--model-size",
                "8b",
                "--fleet",
                "RTX 4090 24GB,H100 80GB",
                "--unified-memory-fraction",
                "0.5",
                "--json",
            ],
        )
        assert r.exit_code == 1 and "unified-memory-fraction" in r.output

    def test_mcp(self):
        from chimeraforge.mcp_server import plan_deployment

        out = plan_deployment(
            model_size="8b",
            hardware="DGX Spark 128GB",
            unified_memory_fraction=0.5,
            gpu_overrides=PRICE,
        )
        assert out["ok"], out
