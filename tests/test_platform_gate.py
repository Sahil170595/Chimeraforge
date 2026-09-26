"""`plan` offers an engine only where its own docs say it runs (per-platform step 3a).

The planner offered every engine on every GPU: vLLM on native Windows, SGLang on
a consumer Radeon card, vLLM AWQ on AMD. The engine-support matrix (0.40.0)
records what each engine's docs say; this pins the gate that enforces it, and
that it refuses only on a documented statement -- silence warns, it never
decides.
"""

from __future__ import annotations

import json

import pytest

from chimeraforge.planner.engine import summarize_trace
from chimeraforge.planner.platform_support import (
    PLATFORM_LINUX_CUDA,
    PLATFORM_LINUX_ROCM,
    PLATFORM_LINUX_XPU,
    PLATFORM_MACOS,
    PLATFORM_WINDOWS,
    PLATFORM_WSL2,
    PlatformError,
    check_engine,
    plan_platform_key,
)
from chimeraforge.planner.service import run_plan

KW = dict(model_size="8b", budget=1e9, quality_target=0.0, latency_slo=1e9)


def _backends(plan) -> set[str]:
    return {c.backend for c in plan.candidates}


def _cells(plan) -> set[tuple[str, str]]:
    return {(c.backend, c.quant) for c in plan.candidates}


class TestVerdicts:
    def test_documented_unsupported_is_refused_with_its_source(self):
        v = check_engine("vllm", PLATFORM_WINDOWS, "nvidia", "geforce", "FP16")
        assert not v.allowed
        assert "does not support Windows natively" in v.reason
        assert "/blob/v0.30.0/" in v.reason

    def test_instinct_only_refuses_radeon_and_allows_instinct(self):
        assert not check_engine("sglang", PLATFORM_LINUX_ROCM, "amd", "radeon", "FP16").allowed
        assert check_engine("sglang", PLATFORM_LINUX_ROCM, "amd", "instinct", "FP16").allowed

    def test_tgi_on_intel_is_data_center_max_only(self):
        assert not check_engine("tgi", PLATFORM_LINUX_XPU, "intel", "arc-pro", "FP16").allowed

    def test_ollama_in_wsl2_is_documented_for_nvidia_only(self):
        assert check_engine("ollama", PLATFORM_WSL2, "nvidia", "geforce", "Q4_K_M").allowed
        assert not check_engine("ollama", PLATFORM_WSL2, "amd", "radeon", "Q4_K_M").allowed

    def test_vllm_on_a_mac_is_cpu_only_so_not_a_gpu_plan(self):
        v = check_engine("vllm", PLATFORM_MACOS, "apple", "", "FP16")
        assert not v.allowed and "CPU only" in v.reason

    @pytest.mark.parametrize(
        "engine,platform,quant",
        [
            ("vllm", PLATFORM_LINUX_ROCM, "AWQ"),
            ("vllm", PLATFORM_LINUX_ROCM, "GPTQ"),
            ("vllm", PLATFORM_LINUX_XPU, "FP8"),
            ("tgi", PLATFORM_LINUX_ROCM, "AWQ"),
        ],
    )
    def test_documented_quant_gaps_are_refused(self, engine, platform, quant):
        vendor, line = ("amd", "instinct") if "rocm" in platform else ("intel", "arc-pro")
        v = check_engine(engine, platform, vendor, line, quant)
        assert not v.allowed and quant in v.reason and "/blob/" in v.reason

    def test_silence_warns_it_does_not_refuse(self):
        v = check_engine("sglang", PLATFORM_WINDOWS, "nvidia", "geforce", "FP16")
        assert v.allowed and any("unverified" in w for w in v.warnings)

    def test_basic_scope_is_a_note_not_a_refusal(self):
        v = check_engine("vllm", PLATFORM_LINUX_XPU, "intel", "arc-pro", "FP16")
        assert v.allowed and any("basic inference" in w for w in v.warnings)

    def test_experimental_warns(self, monkeypatch):
        """No GPU cell is experimental without also being CPU-only today, so the
        rule is pinned against a cell with the status changed."""
        from chimeraforge.planner import platform_support as ps

        data = json.loads(json.dumps(ps.load_engine_support()))
        data["engines"]["ollama"]["platforms"]["linux-xpu"]["status"] = "experimental"
        data["engines"]["ollama"]["platforms"]["linux-xpu"]["scope"] = None
        monkeypatch.setattr(ps, "load_engine_support", lambda: data)
        v = ps.check_engine("ollama", PLATFORM_LINUX_XPU, "intel", "arc-pro", "Q4_K_M")
        assert v.allowed and any("experimental" in w for w in v.warnings)

    def test_conflicting_docs_warn_and_name_the_conflict(self):
        v = check_engine("sglang", PLATFORM_LINUX_ROCM, "amd", "instinct", "GPTQ")
        assert v.allowed and any("disagree" in w for w in v.warnings)

    def test_maintenance_mode_is_said_every_time(self):
        v = check_engine("tgi", PLATFORM_LINUX_CUDA, "nvidia", "datacenter", "FP16")
        assert v.allowed and any("maintenance mode" in w for w in v.warnings)

    def test_unknown_vendor_is_not_refused_but_says_it_was_not_checked(self):
        v = check_engine("vllm", None, "", "", "FP16")
        assert v.allowed and "not checked" in v.warnings[0]


class TestPlatformKey:
    @pytest.mark.parametrize(
        "platform,vendor,row",
        [
            ("linux", "nvidia", PLATFORM_LINUX_CUDA),
            ("linux", "amd", PLATFORM_LINUX_ROCM),
            ("linux", "intel", PLATFORM_LINUX_XPU),
            ("windows", "amd", PLATFORM_WINDOWS),
            ("wsl2", "nvidia", PLATFORM_WSL2),
            ("linux", "", None),
        ],
    )
    def test_mapping(self, platform, vendor, row):
        assert plan_platform_key(platform, vendor) == row

    def test_unknown_os(self):
        with pytest.raises(PlatformError, match="linux, windows, wsl2, macos"):
            plan_platform_key("solaris", "nvidia")

    def test_macos_with_a_discrete_card_is_an_error(self):
        with pytest.raises(PlatformError, match="Apple Silicon"):
            plan_platform_key("macos", "nvidia")


class TestPlans:
    def test_windows_drops_vllm_and_says_why(self):
        plan = run_plan(hardware="RTX 4090 24GB", platform="windows", **KW)
        assert "vllm" not in _backends(plan) and "ollama" in _backends(plan)
        gates = [t for t in plan.trace if t[2] == "platform"]
        assert gates and all("vllm" in t[3] for t in gates)

    def test_linux_nvidia_offers_every_engine(self):
        plan = run_plan(hardware="RTX 4090 24GB", **KW)
        assert _backends(plan) == {"ollama", "vllm", "tgi", "sglang"}
        assert {c.platform for c in plan.candidates} == {PLATFORM_LINUX_CUDA}

    def test_consumer_radeon_drops_sglang_tgi_and_vllm_awq_gptq(self):
        plan = run_plan(hardware="RX 9070 XT 16GB", gpu_overrides={"cost_per_hour": 0.03}, **KW)
        assert not {"sglang", "tgi"} & _backends(plan)
        assert not {("vllm", "AWQ"), ("vllm", "GPTQ")} & _cells(plan)

    def test_instinct_keeps_sglang_and_tgi_but_not_awq_where_documented_missing(self):
        plan = run_plan(hardware="MI300X 192GB", **KW)
        assert {"sglang", "tgi"} <= _backends(plan)
        assert ("vllm", "AWQ") not in _cells(plan) and ("tgi", "AWQ") not in _cells(plan)
        assert ("vllm", "FP16") in _cells(plan)

    def test_unknown_vendor_card_is_planned_with_a_warning(self):
        plan = run_plan(
            hardware="RTX 6090 48GB",
            gpu_overrides={"vram_gb": 48, "bandwidth_gbps": 1300, "cost_per_hour": 0.05},
            **KW,
        )
        assert "vllm" in _backends(plan)
        assert all(any("not checked" in w for w in c.warnings) for c in plan.candidates)

    def test_a_platform_that_blocks_everything_names_the_gate(self):
        trace = [("m", "FP16", "platform", "vllm v0.30.0 does not support windows-native")]
        assert "platform gate" in summarize_trace(trace)[0]


class TestEveryPathCarriesTheKnob:
    """A knob some paths drop is a silent fallback (--quality-from and --gpu-* were
    both lost on --fleet once). Behavioural, per path."""

    def _cli(self, *args):
        from typer.testing import CliRunner

        from chimeraforge.cli import app

        r = CliRunner().invoke(app, ["plan", *args, "--json"])
        assert r.exit_code == 0, r.output
        return json.loads(r.output)

    def test_cli_single_gpu(self):
        out = self._cli(
            "--model-size",
            "8b",
            "--hardware",
            "RTX 4090 24GB",
            "--platform",
            "windows",
            "--budget",
            "1e9",
            "--quality-target",
            "0",
        )
        assert out and "vllm" not in {c["backend"] for c in out}
        assert {c["platform"] for c in out} == {PLATFORM_WINDOWS}

    def test_cli_fleet(self, monkeypatch):
        seen = {}
        from chimeraforge.planner import fleet as fleet_mod

        real = fleet_mod.plan_fleet

        def spy(*a, **kw):
            seen.update(kw.get("plan_kwargs") or {})
            return real(*a, **kw)

        monkeypatch.setattr(fleet_mod, "plan_fleet", spy)
        from typer.testing import CliRunner

        from chimeraforge.cli import app

        CliRunner().invoke(
            app,
            [
                "plan",
                "--model-size",
                "8b",
                "--fleet",
                "RTX 4090 24GB,H100 80GB",
                "--platform",
                "windows",
                "--budget",
                "1e9",
                "--quality-target",
                "0",
                "--json",
            ],
        )
        assert seen.get("platform") == "windows"

    def test_mcp_tool(self):
        from chimeraforge.mcp_server import plan_deployment

        out = plan_deployment(model_size="8b", hardware="RTX 4090 24GB", platform="windows")
        assert out["ok"] and out["platform"] == "windows"
        assert out["recommended"]["backend"] != "vllm"

    def test_mcp_bad_platform_is_an_actionable_error(self):
        from chimeraforge.mcp_server import plan_deployment

        out = plan_deployment(model_size="8b", hardware="RTX 4090 24GB", platform="solaris")
        assert not out["ok"] and "linux, windows, wsl2, macos" in out["error"]


class TestHardwareCarriesVendor:
    @pytest.mark.parametrize(
        "name,vendor,line",
        [
            ("RTX 4090 24GB", "nvidia", "geforce"),
            ("RTX PRO 6000 Blackwell Workstation 96GB", "nvidia", "rtx-pro"),
            ("H100 80GB", "nvidia", "datacenter"),
            ("MI300X 192GB", "amd", "instinct"),
            ("RX 9070 XT 16GB", "amd", "radeon"),
            ("Radeon AI PRO R9700 32GB", "amd", "radeon"),
            ("Arc Pro B60 24GB", "intel", "arc-pro"),
        ],
    )
    def test_vendor_and_line(self, name, vendor, line):
        from chimeraforge.planner.hardware import GPU_DB

        assert (GPU_DB[name].vendor, GPU_DB[name].product_line) == (vendor, line)

    def test_every_bundled_gpu_has_one(self):
        from chimeraforge.planner.hardware import GPU_DB

        assert all(g.vendor and g.product_line for g in GPU_DB.values())
