"""Real native hardware alternatives retain held geometry and honest evidence."""

from __future__ import annotations

import json
from dataclasses import asdict, replace

import pytest
from typer.testing import CliRunner

from chimeraforge import api, plan_study
from chimeraforge.cli import app
from chimeraforge.planner import engine, hardware, service
from chimeraforge.planner.replay import digest, json_value


@pytest.fixture
def source():
    return api.plan(
        api.PlanRequest(
            models=["llama3.2-3b"],
            allow_network=False,
            request_rate=0.1,
            latency_slo=10000,
            quality_target=0,
            budget=1e8,
        )
    )


def case(name, **changes):
    return api.PlanScenario(name, changes)


def test_alternative_rebinds_complete_native_spec_and_matches_ordinary_planner(source, monkeypatch):
    before = source.to_dict()
    original = service.enumerate_candidates
    seen = []

    def search(**kwargs):
        seen.append((kwargs["hardware"], asdict(kwargs["_hardware_spec"]), kwargs["specs"]))
        return original(**kwargs)

    monkeypatch.setattr(service, "enumerate_candidates", search)
    report = api.study_plan(source, [case("larger", hardware="rTx 4090 24gB")]).to_dict()
    row = report["scenarios"][0]
    assert source.to_dict() == before
    assert seen[1][0] == "RTX 4090 24GB"
    assert json_value(seen[1][1]) == json_value(hardware.GPU_DB["RTX 4090 24GB"])
    assert seen[0][2] == seen[1][2]
    monkeypatch.setattr(service, "enumerate_candidates", original)
    ordinary = api.plan(api.PlanRequest(**{**before["inputs"], "hardware": "RTX 4090 24GB"}))
    assert row["candidates"] == ordinary.to_dict()["result"]["candidates"]
    assert row["trace"] == ordinary.to_dict()["result"]["trace"]
    assert row["hardware"]["raw"] == json_value(hardware.GPU_DB["RTX 4090 24GB"])
    assert row["hardware_binding"]["basis"] == "held-registry"
    assert report["base"]["hardware_binding"]["basis"] == "saved-source"
    assert report["frozen_context"]["hardware"] == before["result"]["replay_context"]["hardware"]
    assert row["configuration_switch"]
    assert row["recommended_configuration"]["hardware"] == "RTX 4090 24GB"


def test_native_vram_and_fp8_gates_follow_alternative_geometry():
    source = api.plan(
        api.PlanRequest(
            models=["llama3.1-8b"],
            allow_network=False,
            request_rate=0.1,
            latency_slo=10000,
            quality_target=0,
            budget=1e8,
        )
    )
    report = api.study_plan(
        source,
        [case("small", hardware="RTX 4060 8GB"), case("ampere", hardware="RTX 3090 24GB")],
    ).to_dict()
    small, ampere = report["scenarios"]
    assert small["hardware"]["effective"]["vram_gb"] == 8
    assert any(row[2] == "vram" for row in small["trace"])
    assert not ampere["hardware"]["raw"]["fp8_supported"]
    assert not any(row["quant"] == "FP8" for row in ampere["candidates"])
    assert any("FP8" in str(row) for row in ampere["trace"])
    assert small["candidates"] != report["base"]["candidates"]


def test_platform_compatibility_uses_alternative_vendor_without_changing_saved_platform():
    saved = api.plan(
        api.PlanRequest(platform="windows", allow_network=False, budget=1e8, quality_target=0)
    )
    report = api.study_plan(saved, [case("amd", hardware="MI300X 192GB")]).to_dict()
    row = report["scenarios"][0]
    assert report["frozen_context"]["platform"] == "windows"
    assert row["hardware"]["raw"]["vendor"] == "amd"
    assert any(entry[2] == "platform" for entry in row["trace"])
    assert all(candidate["platform"].startswith("windows") for candidate in row["candidates"])


def test_cross_gpu_timing_is_extrapolated_but_measured_quality_remains(source):
    report = api.study_plan(source, [case("larger", hardware="RTX 4090 24GB")]).to_dict()
    base = next(
        row
        for row in report["base"]["candidates"]
        if row["backend"] == "ollama" and row["quant"] == "FP16"
    )
    changed = next(
        row
        for row in report["scenarios"][0]["candidates"]
        if row["backend"] == "ollama" and row["quant"] == "FP16"
    )
    assert base["provenance"]["throughput"]["class"] == "measured"
    assert changed["provenance"]["throughput"]["class"] == "extrapolated"
    assert changed["provenance"]["quality"] == base["provenance"]["quality"] == "measured"
    assert changed["quality"] == base["quality"]
    assert report["performance"]["state"] == "unverified"


@pytest.mark.parametrize("change", ["geometry", "price", "provenance"])
def test_same_name_spec_identity_detects_physical_changes_only(monkeypatch, change):
    name = "RTX 4090 24GB"
    saved = api.plan(
        api.PlanRequest(
            models=["llama3.2-3b"],
            hardware=name,
            allow_network=False,
            request_rate=0.01,
            latency_slo=100000,
            quality_target=0,
            budget=1e8,
        )
    )
    gpu = hardware.GPU_DB[name]
    updates = (
        {"bandwidth_gbps": gpu.bandwidth_gbps * 1.01}
        if change == "geometry"
        else {"cost_per_hour": gpu.cost_per_hour * 2, "price_basis": "operator-assumed-hourly-cost"}
        if change == "price"
        else {"source_url": "https://example.invalid/new-source", "captured_at": "2026-10-22"}
    )
    monkeypatch.setitem(hardware.GPU_DB, name, replace(gpu, **updates))
    report = api.study_plan(saved, [case("current", hardware=name)]).to_dict()
    before = report["base"]["recommended_configuration"]
    after = report["scenarios"][0]["recommended_configuration"]
    assert {key: value for key, value in before.items() if key != "hardware_spec_sha256"} == {
        key: value for key, value in after.items() if key != "hardware_spec_sha256"
    }
    assert (before["hardware_spec_sha256"] != after["hardware_spec_sha256"]) is (
        change == "geometry"
    )
    assert report["scenarios"][0]["configuration_switch"] is (change == "geometry")


@pytest.mark.parametrize("value", ["auto", "RTX 4090", "missing GPU", "", None, True])
def test_invalid_alternatives_refuse_before_any_search(source, monkeypatch, value):
    monkeypatch.setattr(
        service, "enumerate_candidates", lambda **kwargs: pytest.fail("searched invalid hardware")
    )
    with pytest.raises(api.PlanError, match="hardware|GPU|gpu"):
        api.study_plan(source, [case("bad", hardware=value)])


def test_ambiguous_casefolded_registry_names_refuse_before_search(source, monkeypatch):
    gpu = hardware.GPU_DB["RTX 4090 24GB"]
    monkeypatch.setitem(hardware.GPU_DB, "rtx 4090 24gb", gpu)
    monkeypatch.setattr(
        service, "enumerate_candidates", lambda **kwargs: pytest.fail("searched ambiguous hardware")
    )
    with pytest.raises(api.PlanError, match="ambiguous"):
        api.study_plan(source, [case("bad", hardware=gpu.name)])


@pytest.mark.parametrize("mode", ["cloud", "overrides"])
def test_source_cloud_or_overrides_refuse_explicit_hardware_even_same_name(monkeypatch, mode):
    options = {"cloud": "aws"} if mode == "cloud" else {"gpu_overrides": {"vram_gb": 79}}
    saved = api.plan(
        api.PlanRequest(
            hardware="H100 80GB", allow_network=False, quality_target=0, budget=1e9, **options
        )
    )
    assert (
        api.study_plan(saved, [case("unchanged")]).to_dict()["base"]["hardware"]["raw"]["name"]
        == "H100 80GB"
    )
    monkeypatch.setattr(
        engine, "load_engine_support", lambda: pytest.fail("loaded invalid hardware case")
    )
    with pytest.raises(api.PlanError, match="cloud|overrides"):
        api.study_plan(saved, [case("bad", hardware="H100 80GB")])


def test_hardware_lookup_happens_after_freeze_and_policy_binds_exact_held_snapshot(
    source, monkeypatch
):
    original = plan_study._freeze
    calls = []

    def freeze(inputs):
        calls.append(True)
        monkeypatch.setitem(
            hardware.GPU_DB,
            "RTX 4090 24GB",
            replace(hardware.GPU_DB["RTX 4090 24GB"], bandwidth_gbps=1234),
        )
        return original(inputs)

    monkeypatch.setattr(plan_study, "_freeze", freeze)
    report = api.study_plan(source, [case("held", hardware="RTX 4090 24GB")]).to_dict()
    registry = report["frozen_context"]["hardware_registry"]
    assert calls == [True]
    assert registry["entries"] == json_value(hardware.GPU_DB)
    assert registry["sha256"] == digest(registry["entries"])
    assert report["scenarios"][0]["hardware"]["raw"]["bandwidth_gbps"] == 1234
    assert report["scenarios"][0]["hardware_binding"]["registry_sha256"] == registry["sha256"]


@pytest.mark.parametrize("seam", ["during-freeze", "after-freeze", "between-runs"])
def test_registry_reference_mutation_cannot_return_mixed_identity(source, monkeypatch, seam):
    def mutate():
        name = hardware.REFERENCE_GPU
        monkeypatch.setitem(hardware.GPU_DB, name, replace(hardware.GPU_DB[name], bandwidth_gbps=1))

    if seam == "during-freeze":
        original = engine.load_engine_support

        def load():
            mutate()
            return original()

        monkeypatch.setattr(engine, "load_engine_support", load)
    elif seam == "after-freeze":
        original = plan_study._freeze

        def freeze(inputs):
            result = original(inputs)
            mutate()
            return result

        monkeypatch.setattr(plan_study, "_freeze", freeze)
    else:
        original = service.replay_plan

        def replay(*args, **kwargs):
            result = original(*args, **kwargs)
            mutate()
            return result

        monkeypatch.setattr(service, "replay_plan", replay)
    with pytest.raises(api.PlanError, match="policy.*changed"):
        api.study_plan(source, [case("alt", hardware="RTX 4090 24GB")])


def test_order_invariance_explicit_price_and_unknown_price_are_retained(source, monkeypatch):
    unknown = replace(hardware.GPU_DB["RTX 4090 24GB"], name="Unknown priced card", cost_per_hour=0)
    monkeypatch.setitem(hardware.GPU_DB, unknown.name, unknown)
    cases = [
        case("priced", hardware="RTX 4090 24GB", gpu_cost_per_hour=2),
        case("unknown", hardware=unknown.name),
        case("unaffordable", hardware="RTX 4090 24GB", budget=0),
    ]
    original = source.to_dict()
    left = api.study_plan(source, cases).to_dict()
    right = api.study_plan(source, list(reversed(cases))).to_dict()
    assert {row["name"]: row for row in left["scenarios"]} == {
        row["name"]: row for row in right["scenarios"]
    }
    assert source.to_dict() == original
    priced, unknown_row, refused = left["scenarios"]
    assert priced["hardware"]["raw"]["cost_per_hour"] == 2
    assert priced["price"]["operator_override"]
    assert not unknown_row["feasible"] and any("price" in str(row) for row in unknown_row["trace"])
    assert not refused["feasible"] and refused["trace"]
    assert hardware.GPU_DB["RTX 4090 24GB"].cost_per_hour != 2


def test_sixteen_hardware_cases_complete_and_seventeenth_refuses_before_search(source, monkeypatch):
    cases = [case(str(index), hardware="RTX 4090 24GB") for index in range(16)]
    assert len(api.study_plan(source, cases).to_dict()["scenarios"]) == 16
    monkeypatch.setattr(
        service, "enumerate_candidates", lambda **kwargs: pytest.fail("searched excess cases")
    )
    with pytest.raises(api.PlanError, match="16"):
        api.study_plan(source, cases + [case("extra", hardware="RTX 4090 24GB")])


def test_absent_producer_bundle_cli_api_preserve_geometry_quality_inputs_and_aliases(tmp_path):
    from test_plan_bundle import source_plan

    saved, corpus, quality = source_plan(tmp_path)
    bundle = api.create_plan_bundle(saved, tmp_path / "bundle")
    before = {p: p.read_bytes() for p in bundle._directory.iterdir()}
    corpus.unlink()
    quality.unlink()
    cases = tmp_path / "cases.json"
    cases.write_text(json.dumps([{"name": "larger", "changes": {"hardware": "RTX 4090 24GB"}}]))
    output = tmp_path / "study.json"
    result = CliRunner().invoke(
        app,
        ["study", str(bundle._directory), "--cases", str(cases), "--out", str(output), "--json"],
    )
    assert result.exit_code == 0, result.output
    report = json.loads(result.output)
    assert report == json.loads(output.read_text())
    assert report["scenarios"][0]["hardware"]["raw"]["name"] == "RTX 4090 24GB"
    assert all(p.read_bytes() == raw for p, raw in before.items())
    public = api.study_plan(bundle, [case("larger", hardware="RTX 4090 24GB")])
    assert public.to_dict()["scenarios"][0]["candidates"] == report["scenarios"][0]["candidates"]
    original_quality = report["frozen_context"]["quality_sha256"]
    assert original_quality and all(
        row["quality"] == 0.83 for row in report["scenarios"][0]["candidates"]
    )
    alias = tmp_path / "alias.json"
    alias.hardlink_to(bundle._directory / "plan.json")
    with pytest.raises(api.PlanError, match="cannot replace"):
        public.save(alias)
    assert all(p.read_bytes() == raw for p, raw in before.items())


@pytest.mark.parametrize(
    "invalid",
    ["stale-geometry", "measured-timing", "lost-quality", "lost-refusal", "lost-registry"],
)
def test_installed_consumer_requires_actual_hardware_alternative_semantics(source, invalid):
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "scripts" / "ci_plan_study.py"
    spec = importlib.util.spec_from_file_location("ci_hardware_study_test", path)
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    report = api.study_plan(
        source,
        [
            case("larger", hardware="RTX 4090 24GB"),
            case("no-budget", hardware="RTX 4090 24GB", budget=0),
        ],
    ).to_dict()
    script.validate_hardware(report, source.to_dict())
    changed = report["scenarios"][0]
    if invalid == "stale-geometry":
        changed["hardware"]["raw"] = report["base"]["hardware"]["raw"]
    elif invalid == "measured-timing":
        for row in changed["candidates"]:
            row["provenance"]["throughput"] = {"class": "measured"}
    elif invalid == "lost-quality":
        for row in changed["candidates"]:
            row["provenance"]["quality"] = "unknown"
    elif invalid == "lost-refusal":
        report["scenarios"][1]["trace"] = []
    else:
        report["frozen_context"]["hardware_registry"]["entries"] = {}
    with pytest.raises(AssertionError):
        script.validate_hardware(report, source.to_dict())
