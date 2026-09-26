"""Per-platform serving-engine support, from each engine's own docs.

The planner has offered every engine on every GPU. This pins the matrix that
replaces that assumption: every claim quoted from the engine's docs at a pinned
release tag, silence recorded as silence, and the facts that drive the next step
(enforcement in `plan`) pinned individually so a rebuild cannot quietly flip one.
"""

from __future__ import annotations

import copy
import datetime as dt
import importlib.util
import json
import pathlib

import pytest

from chimeraforge.planner.platform_support import (
    MAX_AGE_DAYS,
    PLATFORM_CPU,
    PLATFORM_LINUX_CUDA,
    PLATFORM_LINUX_ROCM,
    PLATFORM_LINUX_XPU,
    PLATFORM_MACOS,
    PLATFORM_WINDOWS,
    PLATFORM_WSL2,
    engine_support,
    load_engine_support,
    platform_key,
    staleness_warning,
)

ROOT = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def builder():
    spec = importlib.util.spec_from_file_location(
        "build_engine_support", ROOT / "scripts" / "build_engine_support.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestDatasetIsTheBuildersOutput:
    def test_bundled_file_matches_a_rebuild(self, builder):
        text = (ROOT / "src/chimeraforge/planner/data/engine_support.json").read_text(
            encoding="utf-8"
        )
        assert text == builder._text(builder.build())

    def test_every_planner_backend_has_every_platform(self):
        from chimeraforge.planner.constants import BACKENDS

        data = load_engine_support()
        for backend in BACKENDS:
            assert set(data["engines"][backend]["platforms"]) == set(data["platforms"])

    def test_every_claim_is_quoted_and_pinned_to_its_release_tag(self):
        for name, row in load_engine_support()["engines"].items():
            for platform, cell in row["platforms"].items():
                if cell["status"] == "not documented":
                    assert not cell["quote"] and not cell["url"], (name, platform)
                    continue
                assert cell["quote"], (name, platform)
                assert f"/blob/{row['version']}/" in cell["url"], (name, platform)


class TestBuilderFailsLoudly:
    def _build(self, builder, monkeypatch, tmp_path, mutate):
        raw = json.loads((ROOT / "scripts/engine_support_sources.json").read_text(encoding="utf-8"))
        raw = copy.deepcopy(raw)
        mutate(raw)
        p = tmp_path / "sources.json"
        p.write_text(json.dumps(raw), encoding="utf-8")
        monkeypatch.setattr(builder, "SOURCES", p)
        return builder.build()

    def test_a_claim_without_a_quote(self, builder, monkeypatch, tmp_path):
        def drop(raw):
            raw["engines"]["vllm"]["platforms"]["linux-cuda"]["quote"] = ""

        with pytest.raises(builder.EngineSupportError, match="quote"):
            self._build(builder, monkeypatch, tmp_path, drop)

    def test_a_url_not_pinned_to_the_tag(self, builder, monkeypatch, tmp_path):
        def unpin(raw):
            cell = raw["engines"]["vllm"]["platforms"]["linux-cuda"]
            cell["url"] = cell["url"].replace("/blob/v0.30.0/", "/blob/main/")

        with pytest.raises(builder.EngineSupportError, match="pinned"):
            self._build(builder, monkeypatch, tmp_path, unpin)

    def test_silence_cannot_carry_a_claim(self, builder, monkeypatch, tmp_path):
        def claim(raw):
            raw["engines"]["sglang"]["platforms"]["windows-native"] = {
                "status": "not documented",
                "quote": "surely it works",
                "url": "https://example.org",
            }

        with pytest.raises(builder.EngineSupportError, match="no claim"):
            self._build(builder, monkeypatch, tmp_path, claim)

    def test_a_missing_backend(self, builder, monkeypatch, tmp_path):
        def remove(raw):
            del raw["engines"]["tgi"]

        with pytest.raises(builder.EngineSupportError, match="tgi"):
            self._build(builder, monkeypatch, tmp_path, remove)


class TestTheFactsThatDriveEnforcement:
    """Each read off the engine's own docs at its tag (quotes in the dataset)."""

    def test_vllm_does_not_run_natively_on_windows(self):
        assert engine_support("vllm", PLATFORM_WINDOWS).status == "unsupported"
        assert engine_support("vllm", PLATFORM_WSL2).status == "supported"

    def test_vllm_on_rocm_lists_consumer_radeon(self):
        s = engine_support("vllm", PLATFORM_LINUX_ROCM)
        assert s.status == "supported" and s.scope is None
        assert "gfx1200" in s.quote and "gfx1100" in s.quote

    @pytest.mark.parametrize("engine", ["sglang", "tgi"])
    def test_sglang_and_tgi_on_rocm_are_instinct_only(self, engine):
        assert engine_support(engine, PLATFORM_LINUX_ROCM).scope == "instinct-only"

    def test_ollama_is_the_native_windows_engine(self):
        assert engine_support("ollama", PLATFORM_WINDOWS).status == "supported"

    def test_vllm_on_a_mac_is_experimental_and_cpu_only(self):
        s = engine_support("vllm", PLATFORM_MACOS)
        assert (s.status, s.scope) == ("experimental", "cpu-only")

    def test_tgi_is_in_maintenance_mode(self):
        assert "maintenance mode" in engine_support("tgi", PLATFORM_LINUX_CUDA).maintenance

    def test_undocumented_is_not_a_verdict(self):
        assert engine_support("sglang", PLATFORM_WINDOWS).status == "not documented"

    def test_unknown_engine_degrades_to_silence(self):
        assert engine_support("mystery", PLATFORM_CPU).status == "not documented"


class TestPlatformKey:
    @pytest.mark.parametrize(
        "system,vendor,wsl,expected",
        [
            ("Linux", "nvidia", False, PLATFORM_LINUX_CUDA),
            ("Linux", "amd", False, PLATFORM_LINUX_ROCM),
            ("Linux", "intel", False, PLATFORM_LINUX_XPU),
            ("Linux", "nvidia", True, PLATFORM_WSL2),
            ("Linux", None, False, PLATFORM_CPU),
            ("Windows", "amd", False, PLATFORM_WINDOWS),
            ("Darwin", "apple", False, PLATFORM_MACOS),
            ("Darwin", None, False, PLATFORM_CPU),
        ],
    )
    def test_mapping(self, system, vendor, wsl, expected):
        assert platform_key(system, vendor, wsl) == expected


class TestStaleness:
    def test_fresh_snapshot_is_quiet(self):
        captured = dt.date.fromisoformat(load_engine_support()["captured_at"])
        assert staleness_warning(captured + dt.timedelta(days=MAX_AGE_DAYS)) is None

    def test_old_snapshot_says_so(self):
        captured = dt.date.fromisoformat(load_engine_support()["captured_at"])
        w = staleness_warning(captured + dt.timedelta(days=MAX_AGE_DAYS + 1))
        assert w and "build_engine_support" in w


class TestDoctorShowsIt:
    def _run(self, **kw):
        from chimeraforge.doctor import run_doctor

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

    def test_no_gpu_is_the_cpu_row(self):
        r = self._run()
        assert r.platform == PLATFORM_CPU
        assert {s["engine"] for s in r.engine_support} == {"ollama", "vllm", "tgi", "sglang"}

    def test_linux_amd_is_the_rocm_row(self):
        fix = (ROOT / "tests/fixtures/doctor/rocm_smi_meminfo_vram.json").read_text(
            encoding="utf-8"
        )
        r = self._run(
            run=lambda cmd: (0, fix, "") if "rocm-smi" in cmd[0] else (127, "", ""),
            which=lambda n: n if n == "rocm-smi" else None,
        )
        assert r.platform == PLATFORM_LINUX_ROCM
        tgi = next(s for s in r.engine_support if s["engine"] == "tgi")
        assert tgi["scope"] == "instinct-only"

    def test_windows_with_wsl_adds_the_wsl2_row(self):
        r = self._run(system="Windows", which=lambda n: n if n == "wsl" else None)
        assert {s["platform"] for s in r.engine_support} == {PLATFORM_WINDOWS, PLATFORM_WSL2}

    def test_windows_without_wsl_is_native_only(self):
        r = self._run(system="Windows")
        assert {s["platform"] for s in r.engine_support} == {PLATFORM_WINDOWS}


class TestSdistCarriesWhatTheSuiteReads:
    """0.37.0 and 0.39.0 shipped sdists whose suite could not find its own inputs
    (corpora/, scripts/*.json, tests/**/*.csv and *.md were not in MANIFEST.in)."""

    def test_manifest_covers_fixtures_corpora_and_script_data(self, monkeypatch):
        from setuptools._distutils.filelist import FileList

        # FileList matches template patterns against paths relative to the cwd.
        monkeypatch.chdir(ROOT)
        fl = FileList()
        fl.findall()
        for line in (ROOT / "MANIFEST.in").read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                fl.process_template_line(line)
        shipped = {(ROOT / f).resolve() for f in fl.files}
        needed = [
            *(ROOT / "tests" / "fixtures").rglob("*"),
            *(ROOT / "corpora").rglob("*"),
            *(ROOT / "scripts").glob("*.json"),
        ]
        missing = [
            str(p.relative_to(ROOT)) for p in needed if p.is_file() and p.resolve() not in shipped
        ]
        assert not missing, f"not in the sdist: {missing}"
