"""`chimeraforge doctor`: the read-only platform check.

Parsers are golden-tested against real captures (tests/fixtures/doctor/, each
source recorded in SOURCES.md). The orchestration is tested with injected
runners, so every vendor path runs on any machine, and nothing here touches the
real system.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from chimeraforge.doctor import (
    VENDOR_INTEL,
    VENDOR_NVIDIA,
    DetectedGPU,
    ProbeResult,
    assess,
    cuda_version_from_nvml,
    detect_wsl,
    merge_gpus,
    parse_cuda_version_header,
    parse_amd_smi_static,
    parse_amd_smi_version,
    parse_nvidia_smi_query,
    parse_rocm_smi,
    parse_system_profiler_hardware,
    parse_windows_adapters,
    parse_xpu_smi,
    run_doctor,
)

FIX = pathlib.Path(__file__).parent / "fixtures" / "doctor"


def _fixture(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


class TestNvidiaParsers:
    def test_query_csv(self):
        [g] = parse_nvidia_smi_query(_fixture("nvidia_smi_query.csv"))
        assert g.vendor == VENDOR_NVIDIA
        assert g.name == "NVIDIA GeForce RTX 4080 Laptop GPU"
        assert g.vram_gb == 12.0  # 12282 MiB
        assert g.driver == "616.92"

    def test_multi_gpu_lines(self):
        text = _fixture("nvidia_smi_query.csv").strip()
        second = text.replace("0, ", "1, ", 1)
        assert len(parse_nvidia_smi_query(text + "\n" + second)) == 2

    def test_cuda_version_from_the_current_header_spelling(self):
        """This driver prints 'CUDA UMD Version: 13.4', not 'CUDA Version:'."""
        assert parse_cuda_version_header(_fixture("nvidia_smi_header.txt")) == "13.4"

    def test_cuda_version_from_nvml_encoding(self):
        assert cuda_version_from_nvml(13040) == "13.4"
        assert cuda_version_from_nvml(12020) == "12.2"


class TestWindowsParser:
    def test_registry_qword_beats_the_capped_adapter_ram(self):
        """Real capture: AdapterRAM says 4293918720 (uint32 cap) for a 12 GB card;
        the driver's qwMemorySize says 12878610432."""
        gpus = {g.name: g for g in parse_windows_adapters(_fixture("windows_cim_registry.json"))}
        nv = gpus["NVIDIA GeForce RTX 4080 Laptop GPU"]
        assert nv.vram_gb == 12.0
        assert not nv.notes

    def test_integrated_gpu_is_flagged_as_an_aperture(self):
        gpus = {g.name: g for g in parse_windows_adapters(_fixture("windows_cim_registry.json"))}
        igpu = gpus["Intel(R) UHD Graphics"]
        assert igpu.vendor == VENDOR_INTEL
        assert any("aperture" in n for n in igpu.notes)

    def test_capped_adapter_ram_without_qword_is_unknown_not_4gb(self):
        text = json.dumps(
            {
                "adapters": [{"Name": "NVIDIA X", "AdapterRAM": 4293918720, "DriverVersion": "1"}],
                "registry": [],
            }
        )
        [g] = parse_windows_adapters(text)
        assert g.vram_gb is None and "uint32" in g.notes[0]

    def test_single_adapter_object_is_accepted(self):
        """ConvertTo-Json emits an object, not a list, when there is one item."""
        text = json.dumps(
            {
                "adapters": {"Name": "NVIDIA Y", "AdapterRAM": 1, "DriverVersion": "1"},
                "registry": {"DriverDesc": "NVIDIA Y", "HardwareInformation.qwMemorySize": 8 << 30},
            }
        )
        [g] = parse_windows_adapters(text)
        assert g.vram_gb == 8.0


class TestWsl:
    def test_env_var(self):
        assert detect_wsl({"WSL_DISTRO_NAME": "Ubuntu"}, lambda p: None)

    def test_real_wsl2_kernel_release(self):
        """The osrelease string Microsoft staff give as the WSL2 form."""
        release = _fixture("wsl_osrelease.txt")
        seen = []

        def read(path):
            seen.append(path)
            return release

        assert detect_wsl({}, read)
        assert seen == ["/proc/sys/kernel/osrelease"]

    def test_microsoft_alone_is_not_wsl(self):
        """Microsoft staff: 'microsoft' can appear in non-WSL kernel images, so
        only 'WSL' in the release is taken as proof."""
        assert not detect_wsl({}, lambda p: "6.8.0-1015-azure-microsoft")

    def test_plain_linux(self):
        assert not detect_wsl({}, lambda p: "6.8.0-45-generic")


class TestAmdParsers:
    def test_amd_smi_rocm7_wrapper_shape(self):
        gpus = parse_amd_smi_static(_fixture("amd_smi_static_mi300x_rocm721.json"))
        assert len(gpus) == 8
        g = gpus[0]
        assert (g.name, g.vram_gb, g.driver) == ("AMD Instinct MI300X", 192.0, "6.16.13")
        assert g.bandwidth_gbps == 5325.0  # the tool's own vram.max_bandwidth

    def test_amd_smi_pre7_list_shape(self):
        """Before ROCm 7.0 `static --json` was a bare list; AMD's own blog indexes
        it with .[0]. The vram block below is that blog's real output."""
        vram = json.loads(_fixture("amd_smi_vram_fragment_rocm_blog.json"))
        doc = json.dumps([{"asic": {"market_name": "AMD Instinct MI300X"}, "vram": vram}])
        [g] = parse_amd_smi_static(doc)
        assert g.vram_gb == 192.0 and g.bandwidth_gbps is None

    def test_amd_smi_json_after_a_permission_banner(self):
        """Without render-group access amd-smi prints a text warning first."""
        doc = "Permission needed to access required GPU device node(s):\n" + _fixture(
            "amd_smi_static_mi300x_rocm721.json"
        )
        assert len(parse_amd_smi_static(doc)) == 8

    def test_amd_smi_version(self):
        assert parse_amd_smi_version(_fixture("amd_smi_version_rocm721.json")) == {
            "rocm": "7.2.1",
            "amdgpu-driver": "6.16.13",
        }

    def test_amd_smi_error_string_is_not_a_version(self):
        """Non-root: amdgpu_version holds 'AMDSMI_STATUS_FILE_ERROR - ...'."""
        assert parse_amd_smi_version(_fixture("amd_smi_version_nonroot_rocm721.json")) == {
            "rocm": "7.2.1"
        }

    def test_rocm_smi_meminfo(self):
        gpus = parse_rocm_smi(_fixture("rocm_smi_meminfo_vram.json"))
        assert [(g.name, g.vram_gb) for g in gpus] == [("card0", 8.0), ("card1", 0.5)]

    def test_rocm_smi_board_string_is_reported_as_given(self):
        [g] = parse_rocm_smi(_fixture("rocm_smi_productname.json"))
        assert g.name == "AMD INSTINCT MI200 (MCM) OAM LC MBA HPE C2"
        assert assess(g).status == "supply-figures"

    def test_mi300x_via_amd_smi_matches_the_database(self):
        g = parse_amd_smi_static(_fixture("amd_smi_static_mi300x_rocm721.json"))[0]
        s = assess(g)
        assert s.status == "matched" and s.database_entry == "MI300X 192GB"


class TestAppleAndIntelParsers:
    def test_apple_silicon_is_unified_memory(self):
        [g] = parse_system_profiler_hardware(_fixture("system_profiler_hardware_m2.json"))
        assert (g.name, g.vram_gb, g.unified_memory) == ("Apple M2", 16.0, True)
        assert assess(g).status == "not-representable"

    def test_intel_mac_reports_no_apple_chip(self):
        doc = json.dumps({"SPHardwareDataType": [{"cpu_type": "Quad-Core Intel Core i7"}]})
        assert parse_system_profiler_hardware(doc) == []

    def test_xpu_smi_device_detail(self):
        gpus = parse_xpu_smi(_fixture("xpu_smi_discovery_dump_bmg.json"))
        assert len(gpus) == 4
        assert (gpus[0].name, gpus[0].vram_gb) == ("Intel(R) Graphics [0xe211]", 23.9)

    def test_xpu_smi_summary_has_no_memory(self):
        [g] = parse_xpu_smi(_fixture("xpu_smi_discovery_list.json"))
        assert g.vram_gb is None

    def test_pci_id_name_is_not_guessed_into_a_product(self):
        g = parse_xpu_smi(_fixture("xpu_smi_discovery_dump_bmg.json"))[0]
        s = assess(g)
        assert s.status == "supply-figures" and "--gpu-vram-gb 23.9" in s.detail


class TestMergeAndAssess:
    def test_vendor_tool_reading_wins_over_the_windows_route(self):
        nv = DetectedGPU(VENDOR_NVIDIA, "NVIDIA GeForce RTX 4090", 24.0, "1", "nvidia-smi")
        cim = DetectedGPU(VENDOR_NVIDIA, "NVIDIA GeForce RTX 4090", None, "2", "windows-cim")
        merged = merge_gpus(
            [ProbeResult("nvidia-smi", True, "", [nv]), ProbeResult("windows-cim", True, "", [cim])]
        )
        assert merged == [nv]

    def test_known_nvidia_card_is_matched_for_auto(self):
        s = assess(DetectedGPU(VENDOR_NVIDIA, "NVIDIA GeForce RTX 4090", 24.0, "1", "nvidia-smi"))
        assert s.status == "matched" and s.database_entry == "RTX 4090 24GB"
        assert "--hardware auto" in s.detail

    def test_known_non_nvidia_card_names_the_entry_because_auto_is_nvidia_only(self):
        s = assess(DetectedGPU("amd", "AMD Radeon RX 9070 XT", 16.0, None, "windows-cim"))
        assert s.database_entry == "RX 9070 XT 16GB"
        assert '--hardware "RX 9070 XT 16GB"' in s.detail

    def test_matched_part_with_no_vendor_price_says_so(self):
        s = assess(DetectedGPU("amd", "AMD Radeon AI PRO R9700", 32.0, None, "windows-cim"))
        assert s.status == "matched" and "--gpu-price-per-hour" in s.detail

    def test_unknown_card_gets_the_flags_not_a_guess(self):
        s = assess(DetectedGPU(VENDOR_NVIDIA, "NVIDIA RTX 9999", 48.0, None, "nvidia-smi"))
        assert s.status == "supply-figures"
        assert "--gpu-vram-gb 48" in s.detail and "<vendor GB/s>" in s.detail

    def test_aperture_vram_is_not_offered_as_a_flag_value(self):
        g = DetectedGPU(VENDOR_INTEL, "Intel(R) UHD Graphics", 2.0, None, "windows-cim")
        g.notes.append("shared-memory aperture")
        assert "--gpu-vram-gb <GB>" in assess(g).detail

    def test_unified_memory_device_is_not_representable_yet(self):
        g = DetectedGPU(
            "apple", "Apple M4 Max", 128.0, None, "system_profiler", unified_memory=True
        )
        assert assess(g).status == "not-representable"


def _fake(outputs: dict[str, tuple[int, str, str]]):
    calls: list[list[str]] = []

    def run(cmd):
        calls.append(cmd)
        key = pathlib.Path(cmd[0]).stem
        if key in ("powershell", "pwsh"):
            key = "powershell"
        return outputs.get(key, (127, "", "not found"))

    return run, calls


def _offline(**kw):
    """run_doctor with no real system access unless a test supplies it."""
    base = dict(
        run=lambda cmd: (127, "", ""),
        which=lambda n: None,
        system="Linux",
        env={},
        read_text=lambda p: None,
        check_engines=False,
        nvml=lambda: None,
    )
    base.update(kw)
    return run_doctor(**base)


class TestRunDoctor:
    def test_windows_nvidia_machine(self):
        run, _ = _fake(
            {
                "nvidia-smi": (0, _fixture("nvidia_smi_query.csv"), ""),
                "powershell": (0, _fixture("windows_cim_registry.json"), ""),
            }
        )
        r = _offline(
            run=run,
            which=lambda n: n if n in ("nvidia-smi", "powershell") else None,
            system="Windows",
        )
        assert [g.name for g in r.gpus] == [
            "NVIDIA GeForce RTX 4080 Laptop GPU",
            "Intel(R) UHD Graphics",
        ]
        assert r.planner[0].database_entry == "RTX 4080 12GB"

    def test_linux_amd_machine_prefers_amd_smi(self):
        run, calls = _fake(
            {
                "amd-smi": (0, _fixture("amd_smi_static_mi300x_rocm721.json"), ""),
            }
        )

        def run2(cmd):
            if cmd[1:2] == ["version"]:
                return 0, _fixture("amd_smi_version_rocm721.json"), ""
            return run(cmd)

        r = _offline(run=run2, which=lambda n: n if n in ("amd-smi", "rocm-smi") else None)
        amd = next(p for p in r.probes if p.tool == "amd-smi")
        assert amd.found and amd.runtime["rocm"] == "7.2.1"
        assert len(r.gpus) == 8
        assert not any(c[0] == "rocm-smi" for c in calls)

    def test_linux_falls_back_to_rocm_smi(self):
        run, _ = _fake({"rocm-smi": (0, _fixture("rocm_smi_meminfo_vram.json"), "")})
        r = _offline(run=run, which=lambda n: n if n == "rocm-smi" else None)
        assert [g.vram_gb for g in r.gpus] == [8.0, 0.5]

    def test_rocm_smi_exit_zero_with_nothing_is_not_found(self):
        """rocm-smi exits 0 and prints 'No JSON data to report' without a driver."""
        run, _ = _fake({"rocm-smi": (0, "No JSON data to report\n", "")})
        r = _offline(run=run, which=lambda n: n if n == "rocm-smi" else None)
        probe = next(p for p in r.probes if p.tool == "rocm-smi")
        assert not probe.found and "No JSON data" in probe.detail

    def test_intel_summary_then_per_device_query(self):
        detail = json.loads(_fixture("xpu_smi_discovery_dump_bmg.json"))["device_list"][0]

        def run(cmd):
            if "-d" in cmd:
                return 0, json.dumps(detail), ""
            return 0, _fixture("xpu_smi_discovery_list.json"), ""

        r = _offline(run=run, which=lambda n: n if n == "xpu-smi" else None)
        assert [g.vram_gb for g in r.gpus] == [23.9]

    def test_macos_apple_silicon(self):
        run, _ = _fake({"system_profiler": (0, _fixture("system_profiler_hardware_m2.json"), "")})
        r = _offline(
            run=run, which=lambda n: n if n == "system_profiler" else None, system="Darwin"
        )
        assert r.gpus[0].unified_memory and r.planner[0].status == "not-representable"

    def test_no_tools_is_a_finding_not_an_error(self):
        r = _offline()
        assert not r.gpus and r.notes and not r.wsl
        assert all(not p.found and p.detail for p in r.probes)

    def test_cuda_version_falls_back_to_the_header_without_nvml(self):
        def run(cmd):
            if len(cmd) == 1:
                return 0, _fixture("nvidia_smi_header.txt"), ""
            return 0, _fixture("nvidia_smi_query.csv"), ""

        r = _offline(run=run, which=lambda n: n if n == "nvidia-smi" else None)
        assert r.probes[0].runtime == {"cuda": "13.4", "nvidia-driver": "616.92"}

    def test_a_failing_tool_reports_why(self):
        r = _offline(
            run=lambda cmd: (9, "", "NVIDIA-SMI has failed because it could not communicate"),
            which=lambda n: n,
        )
        assert "could not communicate" in r.probes[0].detail

    def test_it_only_reads(self):
        """Every command the doctor issues is a query; none takes an action flag."""
        run, calls = _fake({"nvidia-smi": (0, _fixture("nvidia_smi_query.csv"), "")})
        _offline(run=run, which=lambda n: n)
        flat = " ".join(" ".join(c) for c in calls).lower()
        for verb in ("--gpu-reset", "-pm ", "--persistence", "reset", "--set"):
            assert verb not in flat


class _Engine:
    def __init__(self, url, healthy, version):
        self.base_url, self._healthy, self._version = url, healthy, version

    async def health_check(self):
        return self._healthy, "healthy" if self._healthy else "not running"

    async def get_version(self):
        return self._version

    async def close(self):
        pass


class TestEngineIdentity:
    def test_a_healthy_port_that_does_not_identify_is_not_the_engine(self, monkeypatch):
        """Real case on the dev box: a generic uvicorn app on :8000 answered
        /health 200, and the vLLM adapter read that as 'vLLM is running'."""
        from chimeraforge import doctor as mod

        monkeypatch.setattr(
            "chimeraforge.bench.backends.get_backend",
            lambda name, **kw: _Engine("http://localhost:8000", True, None),
        )
        [e] = mod.probe_engines(("vllm",))
        assert e.answered and not e.running
        assert "did not identify" in e.detail

    def test_an_engine_that_names_itself_is_running(self, monkeypatch):
        from chimeraforge import doctor as mod

        monkeypatch.setattr(
            "chimeraforge.bench.backends.get_backend",
            lambda name, **kw: _Engine("http://localhost:11434", True, "0.32.1"),
        )
        [e] = mod.probe_engines(("ollama",))
        assert e.running and e.version == "0.32.1"

    def test_nothing_listening_is_not_running(self, monkeypatch):
        from chimeraforge import doctor as mod

        monkeypatch.setattr(
            "chimeraforge.bench.backends.get_backend",
            lambda name, **kw: _Engine("http://localhost:8080", False, None),
        )
        [e] = mod.probe_engines(("tgi",))
        assert not e.running and not e.answered


class TestCli:
    def _patch(self, monkeypatch, **kw):
        from chimeraforge import doctor as mod

        monkeypatch.setattr(mod, "run_doctor", lambda check_engines=True: _offline(**kw))

    def test_json_report(self, monkeypatch):
        from typer.testing import CliRunner

        from chimeraforge.cli import app

        run, _ = _fake({"nvidia-smi": (0, _fixture("nvidia_smi_query.csv"), "")})
        self._patch(monkeypatch, run=run, which=lambda n: n if n == "nvidia-smi" else None)
        r = CliRunner().invoke(app, ["doctor", "--json", "--no-engines"])
        assert r.exit_code == 0, r.output
        data = json.loads(r.output)
        assert data["planner"][0]["database_entry"] == "RTX 4080 12GB"

    @pytest.mark.parametrize("args", [[], ["--no-engines"]])
    def test_table_renders(self, monkeypatch, args):
        from typer.testing import CliRunner

        from chimeraforge.cli import app

        self._patch(monkeypatch)
        r = CliRunner().invoke(app, ["doctor", *args])
        assert r.exit_code == 0 and "Detection" in r.output
