"""Frozen-context scenario comparisons use real shared search and truthful units."""

from __future__ import annotations

import copy
import json
from dataclasses import asdict

import pytest
from typer.testing import CliRunner

from chimeraforge import api
from chimeraforge.cli import app
from chimeraforge.plan_check import compare
from chimeraforge.planner import engine, service


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
            grid_region="USA",
        )
    )


def scenario(name, **changes):
    return api.PlanScenario(name=name, changes=changes)


def test_real_study_retains_infeasible_cases_and_native_deltas(source):
    original = source.to_dict()
    report = api.study_plan(
        source,
        [scenario("same"), scenario("half-duty", duty_cycle=0.5), scenario("no-budget", budget=0)],
    ).to_dict()
    assert source.to_dict() == original
    assert report["source_fingerprint"] == original["fingerprint"]
    assert report["base"]["feasible"]
    assert report["scenarios"][0]["comparison"]["changed"] is False
    half = report["scenarios"][1]
    assert half["comparison"]["matched"]
    delta = half["comparison"]["matched"][0]["deltas"]["tokens_served_month"]
    assert delta["unit"] == "tokens/month" and delta["delta"] < 0
    refused = report["scenarios"][2]
    assert not refused["feasible"] and refused["trace"]
    assert refused["recommended"] is None and refused["comparison"]["feasibility"] == "lost"
    assert report["performance"]["state"] == "unverified" and report["exit_code"] == 0


def test_scenarios_equal_shared_ordinary_plans_not_an_alternative_engine(source):
    changes = {"request_rate": 2.0, "context_length": 4096, "avg_tokens": 64, "budget": 300}
    report = api.study_plan(source, [scenario("changed", **changes)]).to_dict()
    request = {**source.to_dict()["inputs"], **changes}
    ordinary = api.plan(api.PlanRequest(**request)).to_dict()["result"]
    assert report["scenarios"][0]["candidates"] == ordinary["candidates"]
    assert report["scenarios"][0]["trace"] == ordinary["trace"]
    assert report["scenarios"][0]["comparison"] == compare(
        report["base"]["candidates"], ordinary["candidates"]
    )


def test_context_and_selected_batch_settings_are_visible_configuration_changes(source):
    report = api.study_plan(source, [scenario("larger-context", context_length=4096)]).to_dict()
    row = report["scenarios"][0]
    assert report["base"]["recommended_configuration"]["context_length"] == 2048
    assert row["recommended_configuration"]["context_length"] == 4096
    assert (
        row["recommended_configuration"]["effective_batch"] == row["recommended"]["effective_batch"]
    )
    assert row["configuration_switch"] is True


def test_current_sources_captured_once_and_geometry_never_resolved_again(source, monkeypatch):
    calls = {"support": 0, "grid": 0}
    support = engine.load_engine_support()
    original_grid = service.grid_intensity

    def get_support():
        calls["support"] += 1
        assert calls["support"] == 1
        return support

    def get_grid(*args, **kwargs):
        calls["grid"] += 1
        assert calls["grid"] == 1
        return original_grid(*args, **kwargs)

    monkeypatch.setattr(engine, "load_engine_support", get_support)
    monkeypatch.setattr(service, "grid_intensity", get_grid)
    monkeypatch.setattr(
        service, "resolve_spec", lambda *a, **k: pytest.fail("resolved saved model")
    )
    report = api.study_plan(source, [scenario("one"), scenario("two")]).to_dict()
    assert calls == {"support": 1, "grid": 1}
    assert report["scenarios"][0]["candidates"] == report["scenarios"][1]["candidates"]
    assert report["frozen_context"]["engine_support"]["sha256"]
    assert report["frozen_context"]["grid"]["region"] == "USA"


def test_cloud_and_quarantine_consumed_once_and_staleness_is_frozen(monkeypatch):
    saved = api.plan(
        api.PlanRequest(
            models=["llama3.2-3b"],
            hardware="H100 80GB",
            cloud="aws",
            use_contributions=True,
            allow_network=False,
            quality_target=0,
            budget=1e9,
        )
    )
    snapshot = engine.load_cloud_prices()
    support = engine.load_engine_support()
    counts = {"cloud": 0, "quarantine": 0, "stale": 0}
    real_stale = engine.cloud_is_stale

    def cloud():
        counts["cloud"] += 1
        assert counts["cloud"] == 1
        return snapshot

    def quarantine():
        counts["quarantine"] += 1
        assert counts["quarantine"] == 1
        return []

    def stale(*args, **kwargs):
        counts["stale"] += 1
        assert counts["stale"] == 1
        return real_stale(*args, **kwargs)

    monkeypatch.setattr(engine, "load_cloud_prices", cloud)
    monkeypatch.setattr(engine, "load_quarantine", quarantine)
    monkeypatch.setattr(engine, "cloud_is_stale", stale)
    monkeypatch.setattr(engine, "load_engine_support", lambda: support)
    report = api.study_plan(saved, [scenario("one"), scenario("two")]).to_dict()
    assert counts == {"cloud": 1, "quarantine": 1, "stale": 1}
    assert report["frozen_context"]["cloud"]["captured_at"] == snapshot["captured_at"]
    assert (
        report["frozen_context"]["contributions"]["trust"]
        == "quarantined unsigned third-party evidence"
    )


def test_loader_mutation_during_search_cannot_substitute_frozen_support(source, monkeypatch):
    data = copy.deepcopy(engine.load_engine_support())
    original = service.enumerate_candidates

    def search(**kwargs):
        result = original(**kwargs)
        data["engines"].clear()
        return result

    monkeypatch.setattr(engine, "load_engine_support", lambda: data)
    monkeypatch.setattr(service, "enumerate_candidates", search)
    report = api.study_plan(source, [scenario("same"), scenario("same-again")]).to_dict()
    assert report["base"]["candidates"] == report["scenarios"][0]["candidates"]
    assert report["scenarios"][0]["candidates"] == report["scenarios"][1]["candidates"]


def test_policy_change_mid_search_refuses_instead_of_mixing_cases(source, monkeypatch):
    original = service.enumerate_candidates

    def search(**kwargs):
        result = original(**kwargs)
        monkeypatch.setattr(engine, "MAX_REPLICAS", engine.MAX_REPLICAS + 1)
        return result

    monkeypatch.setattr(service, "enumerate_candidates", search)
    with pytest.raises(api.PlanError, match="policy.*changed"):
        api.study_plan(source, [scenario("same")])


@pytest.mark.parametrize(
    "changes",
    [
        {"hardware": "H100 80GB"},
        {"models": ["other"]},
        {"platform": "macos"},
        {"allow_network": True},
        {"models_path": "other.json"},
        {"gpu_overrides": {"vram_gb": 1}},
        {"request_rate": True},
        {"request_rate": -1},
        {"request_rate": float("nan")},
        {"context_length": 1.5},
        {"duty_cycle": 0},
        {"gpu_cost_per_hour": -1},
    ],
)
def test_invalid_or_unsupported_cases_refused_before_loading(source, changes, monkeypatch):
    monkeypatch.setattr(
        engine, "load_engine_support", lambda: pytest.fail("loaded before validation")
    )
    with pytest.raises(api.PlanError):
        api.study_plan(source, [api.PlanScenario("bad", changes)])


def test_duplicate_names_empty_or_too_many_cases_refused(source):
    for cases in ([], [scenario("same"), scenario("same")], [scenario(str(i)) for i in range(17)]):
        with pytest.raises(api.PlanError):
            api.study_plan(source, cases)


def test_explicit_price_scenario_changes_bound_cost_not_physical_hardware(source):
    report = api.study_plan(source, [scenario("expensive", gpu_cost_per_hour=2.0)]).to_dict()
    row = report["scenarios"][0]
    assert row["changes"]["gpu_cost_per_hour"] == 2
    assert row["comparison"]["matched"][0]["deltas"]["monthly_cost"]["delta"] > 0
    assert (
        row["hardware"]["effective"]["vram_gb"]
        == report["base"]["hardware"]["effective"]["vram_gb"]
    )
    assert row["hardware"]["raw"]["cost_per_hour"] == 2.0


def test_bundle_study_after_original_inputs_deleted(tmp_path):
    corpus = tmp_path / "coefficients.json"
    quality = tmp_path / "private-harness.json"
    corpus.write_text('{"vram":{"overhead_factor":1.12}}', encoding="utf-8")
    quality.write_text(
        json.dumps({"results": {"mmlu": {"acc,none": 0.83}}, "n-samples": {"mmlu": 5000}})
    )
    saved = api.plan(
        api.PlanRequest(
            models=["llama3.2-3b"],
            models_path=str(corpus),
            quality_from=str(quality),
            allow_network=False,
            quality_target=0,
            budget=1e8,
        )
    )
    path = tmp_path / "plan.json"
    saved.save(path)
    bundle = api.create_plan_bundle(path, tmp_path / "handoff")
    original = path.read_bytes()
    corpus.unlink()
    quality.unlink()
    report = api.study_plan(
        bundle, [scenario("same"), scenario("larger", context_length=4096)]
    ).to_dict()
    assert path.read_bytes() == original
    assert report["base"]["candidates"] == saved.to_dict()["result"]["candidates"]
    assert report["frozen_context"]["inputs"]["corpus"]["state"] == "verified_content"
    assert "private-harness.json" in json.dumps(report["frozen_context"]["inputs"])


def test_legacy_missing_frozen_binding_refused(source):
    data = source.to_dict()
    data["schema_version"] = 1
    data["result"].pop("replay_context")
    data.pop("fingerprint")
    data["fingerprint"] = api._digest(data)
    legacy = api.artifact_from_dict(data)
    with pytest.raises(api.PlanError, match="bound replay"):
        api.study_plan(legacy, [scenario("same")])


def test_cli_public_study_infeasible_is_a_completed_operation(tmp_path, source):
    path = tmp_path / "plan.json"
    source.save(path)
    original = path.read_bytes()
    cases = tmp_path / "cases.json"
    cases.write_text('[{"name":"no-budget","changes":{"budget":0}}]')
    out = tmp_path / "study.json"
    result = CliRunner().invoke(
        app, ["study", str(path), "--cases", str(cases), "--out", str(out), "--json"]
    )
    assert result.exit_code == 0, result.output
    report = json.loads(result.output)
    assert report["scenarios"][0]["feasible"] is False
    assert json.loads(out.read_text()) == report and path.read_bytes() == original
    cases.write_text('[{"name":"bad","changes":{"allow_network":true}}]')
    invalid = CliRunner().invoke(app, ["study", str(path), "--cases", str(cases), "--json"])
    assert invalid.exit_code == 2 and "error" in json.loads(invalid.output)


def test_report_defensive_copy_and_python_type_introspection(source):
    from typing import get_type_hints

    result = api.study_plan(source, [scenario("same")])
    report = result.to_dict()
    report["base"]["candidates"].clear()
    assert result.to_dict()["base"]["candidates"]
    assert get_type_hints(api.study_plan)["return"] is api.PlanStudy
    assert asdict(scenario("typed", duty_cycle=0.5))["changes"] == {"duty_cycle": 0.5}


def test_nonempty_quarantine_retains_unsigned_provenance_and_exact_record_freeze(monkeypatch):
    from chimeraforge import contrib
    from test_contributions import bench_result

    measured = bench_result()
    measured["environment"]["gpu_memory_gb"] = 24
    contribution = contrib.build_contribution(measured)
    rows = [contribution]
    monkeypatch.setattr(engine, "load_quarantine", lambda: rows)
    saved = api.plan(
        api.PlanRequest(
            models=["llama3.2-3b"],
            hardware="RTX 4090 24GB",
            use_contributions=True,
            allow_network=False,
            quality_target=0,
            budget=1e8,
        )
    )
    original_search = service.enumerate_candidates

    def search(**kwargs):
        result = original_search(**kwargs)
        rows[0]["measurements"]["decode_tps_mean"] = 10000
        return result

    monkeypatch.setattr(service, "enumerate_candidates", search)
    report = api.study_plan(saved, [scenario("same"), scenario("same-again")]).to_dict()
    assert report["frozen_context"]["contributions"]["records"][0]["id"] == contribution["id"]
    assert report["base"]["used_contribution_ids"] == [contribution["id"]]
    assert report["base"]["candidates"] == report["scenarios"][0]["candidates"]
    assert report["scenarios"][0]["candidates"] == report["scenarios"][1]["candidates"]
    selected = next(
        row
        for row in report["scenarios"][1]["candidates"]
        if row["backend"] == "vllm" and row["quant"] == "FP16"
    )
    assert selected["throughput_tps"] == 150
    assert selected["provenance"]["throughput"]["class"] == "contributed"
    assert report["source_authentication"] == "unverified"


def test_external_corpus_and_quality_overwritten_after_capture_stay_frozen(tmp_path, monkeypatch):
    corpus, quality = tmp_path / "coeff.json", tmp_path / "quality.json"
    corpus.write_text('{"vram":{"overhead_factor":1.123}}')
    quality.write_text('{"results":{"mmlu":{"acc,none":0.83}},"n-samples":{"mmlu":5000}}')
    saved = api.plan(
        api.PlanRequest(
            models=["llama3.2-3b"],
            models_path=str(corpus),
            quality_from=str(quality),
            allow_network=False,
            quality_target=0,
            budget=1e8,
        )
    )
    original_search = service.enumerate_candidates
    seen = []

    def search(**kwargs):
        seen.append((kwargs["models"].vram.overhead_factor, kwargs["quality_override"].score))
        corpus.write_text('{"vram":{"overhead_factor":9}}')
        quality.write_text('{"results":{"mmlu":{"acc,none":0.01}},"n-samples":{"mmlu":5000}}')
        return original_search(**kwargs)

    monkeypatch.setattr(service, "enumerate_candidates", search)
    report = api.study_plan(saved, [scenario("same"), scenario("same-again")]).to_dict()
    assert seen == [(1.123, 0.83)] * 3
    assert report["base"]["candidates"] == report["scenarios"][1]["candidates"]
    assert json.loads(corpus.read_text())["vram"]["overhead_factor"] == 9
    assert json.loads(quality.read_text())["results"]["mmlu"]["acc,none"] == 0.01


@pytest.mark.parametrize("days,stale", [(90, False), (91, True)])
def test_cloud_expiry_and_engine_support_clock_use_one_observed_date(monkeypatch, days, stale):
    from datetime import date, timedelta
    from types import SimpleNamespace
    from chimeraforge import plan_study

    saved = api.plan(
        api.PlanRequest(
            models=["llama3.2-3b"],
            hardware="H100 80GB",
            cloud="aws",
            allow_network=False,
            quality_target=0,
            budget=1e9,
        )
    )
    snapshot = engine.load_cloud_prices()
    observed = date.fromisoformat(snapshot["captured_at"]) + timedelta(days=days)
    monkeypatch.setattr(plan_study, "date", SimpleNamespace(today=lambda: observed))
    report = api.study_plan(saved, [scenario("same"), scenario("same-again")]).to_dict()
    assert report["frozen_context"]["cloud"]["age_days"] == days
    assert report["frozen_context"]["cloud"]["stale"] is stale
    assert report["frozen_context"]["as_of_date"] == observed.isoformat()
    assert report["scenarios"][0]["candidates"] == report["scenarios"][1]["candidates"]


@pytest.mark.parametrize("kind", ["moe", "hybrid", "mla"])
def test_full_geometry_is_bound_for_every_case(monkeypatch, kind):
    from chimeraforge.planner.resolver import ModelSpec, SOURCE_HF

    extra = {
        "moe": {"num_experts": 8, "experts_per_token": 2, "moe_intermediate_size": 1024},
        "hybrid": {"n_attention_layers": 4, "recurrent_state_bytes_per_seq": 1048576.0},
        "mla": {"kv_lora_rank": 512, "qk_rope_head_dim": 64},
    }[kind]
    spec = ModelSpec("test/full", 3.0, 8, 8, 128, hidden_size=1024, source=SOURCE_HF, **extra)
    monkeypatch.setattr(service, "resolve_spec", lambda *a, **k: spec)
    saved = api.plan(
        api.PlanRequest(models=[spec.name], allow_network=False, quality_target=0, budget=1e8)
    )
    monkeypatch.setattr(service, "resolve_spec", lambda *a, **k: pytest.fail("substituted model"))
    original_search = service.enumerate_candidates
    seen = []

    def search(**kwargs):
        seen.append(asdict(kwargs["specs"][spec.name]))
        return original_search(**kwargs)

    monkeypatch.setattr(service, "enumerate_candidates", search)
    api.study_plan(saved, [scenario("same"), scenario("longer", context_length=4096)])
    assert seen == [asdict(spec)] * 3


def test_auto_unified_gpu_never_probes_or_applies_fraction_twice(monkeypatch):
    gpu = service.GPUSpec(
        "Study unified",
        64,
        400,
        0.01,
        fp16_tflops=20,
        vendor="apple",
        unified_memory=True,
        memory_options_gb=(64,),
    )
    monkeypatch.setitem(engine.GPU_DB, gpu.name, gpu)
    monkeypatch.setattr(engine, "resolve_hardware", lambda *a, **k: (gpu, []))
    monkeypatch.setattr(service, "local_plan_platform", lambda: "macos")
    saved = api.plan(
        api.PlanRequest(hardware="auto", unified_memory_fraction=0.5, allow_network=False)
    )
    monkeypatch.setattr(engine, "resolve_hardware", lambda *a, **k: pytest.fail("reprobed host"))
    report = api.study_plan(saved, [scenario("same"), scenario("same-again")]).to_dict()
    assert report["base"]["hardware"]["raw"]["vram_gb"] == 64
    assert all(row["hardware"]["effective"]["vram_gb"] == 32 for row in report["scenarios"])


def test_explicit_zero_price_is_unknown_not_free(source):
    report = api.study_plan(source, [scenario("unknown-price", gpu_cost_per_hour=0)]).to_dict()
    row = report["scenarios"][0]
    assert not row["feasible"] and any("price" in entry[3] for entry in row["trace"])
    assert (
        row["price"]["operator_override"]
        and row["price"]["basis"] == "operator-assumed-hourly-cost"
    )


@pytest.mark.parametrize("target", ["plan", "cases", "corpus", "quality", "bundle"])
def test_output_cannot_replace_any_known_input(tmp_path, target):
    corpus, quality = tmp_path / "corpus.json", tmp_path / "quality.json"
    corpus.write_text('{"vram":{"overhead_factor":1.12}}')
    quality.write_text('{"results":{"mmlu":{"acc,none":0.83}},"n-samples":{"mmlu":5000}}')
    saved = api.plan(
        api.PlanRequest(models_path=str(corpus), quality_from=str(quality), allow_network=False)
    )
    plan_path, cases = tmp_path / "plan.json", tmp_path / "cases.json"
    saved.save(plan_path)
    cases.write_text('[{"name":"same","changes":{}}]')
    bundle = api.create_plan_bundle(plan_path, tmp_path / "bundle")
    targets = {
        "plan": plan_path,
        "cases": cases,
        "corpus": corpus,
        "quality": quality,
        "bundle": bundle._directory / "corpus.json",
    }
    output = targets[target]
    original = output.read_bytes()
    source = bundle._directory if target == "bundle" else plan_path
    result = CliRunner().invoke(
        app, ["study", str(source), "--cases", str(cases), "--out", str(output), "--json"]
    )
    assert result.exit_code == 2 and output.read_bytes() == original


@pytest.mark.parametrize(
    "raw",
    [
        b'{"bad":1}',
        b'[{"name":"same","changes":{},"extra":0}]',
        b'[{"name":"same","name":"substituted","changes":{}}]',
        b"[" * 5000,
    ],
)
def test_cli_malformed_cases_are_domain_errors(tmp_path, source, raw):
    saved, cases = tmp_path / "plan.json", tmp_path / "cases.json"
    source.save(saved)
    cases.write_bytes(raw)
    result = CliRunner().invoke(app, ["study", str(saved), "--cases", str(cases), "--json"])
    assert result.exit_code == 2 and "error" in json.loads(result.output)


def test_cloud_hourly_gpu_override_refuses_before_current_cloud_load(monkeypatch):
    saved = api.plan(api.PlanRequest(hardware="H100 80GB", cloud="aws", allow_network=False))
    monkeypatch.setattr(
        engine, "load_cloud_prices", lambda: pytest.fail("read cloud for invalid case")
    )
    with pytest.raises(api.PlanError, match="cloud instance"):
        api.study_plan(saved, [scenario("invalid-price", gpu_cost_per_hour=2)])


def test_hardware_registry_changes_abort_the_study(source, monkeypatch):
    from dataclasses import replace

    original = service.enumerate_candidates
    gpu_name = source.to_dict()["result"]["replay_context"]["hardware"]["raw"]["name"]

    def search(**kwargs):
        result = original(**kwargs)
        monkeypatch.setitem(
            engine.GPU_DB, gpu_name, replace(engine.GPU_DB[gpu_name], bandwidth_gbps=1)
        )
        return result

    monkeypatch.setattr(service, "enumerate_candidates", search)
    with pytest.raises(api.PlanError, match="policy.*changed"):
        api.study_plan(source, [scenario("same")])


@pytest.mark.parametrize("input_kind", ["corpus", "quality"])
def test_changed_original_bytes_refused_before_planning(tmp_path, monkeypatch, input_kind):
    path = tmp_path / "input.json"
    original = (
        '{"vram":{"overhead_factor":1.12}}'
        if input_kind == "corpus"
        else '{"results":{"mmlu":{"acc,none":0.83}},"n-samples":{"mmlu":5000}}'
    )
    path.write_text(original)
    option = "models_path" if input_kind == "corpus" else "quality_from"
    saved = api.plan(api.PlanRequest(**{option: str(path)}, allow_network=False))
    path.write_text(original + " ")
    monkeypatch.setattr(engine, "load_engine_support", lambda: pytest.fail("planned changed input"))
    with pytest.raises(api.PlanError, match="bytes changed"):
        api.study_plan(saved, [scenario("same")])


def test_source_plan_hardlink_output_alias_refused(tmp_path, source):
    saved, alias, cases = tmp_path / "saved.json", tmp_path / "alias.json", tmp_path / "cases.json"
    source.save(saved)
    alias.hardlink_to(saved)
    cases.write_text('[{"name":"same","changes":{}}]')
    original = saved.read_bytes()
    result = CliRunner().invoke(
        app, ["study", str(saved), "--cases", str(cases), "--out", str(alias), "--json"]
    )
    assert result.exit_code == 2 and saved.read_bytes() == original


@pytest.mark.parametrize("role", ["corpus", "quality"])
@pytest.mark.parametrize("hardlink", [False, True])
def test_bundle_study_cannot_overwrite_native_producer_input(tmp_path, monkeypatch, role, hardlink):
    from test_plan_bundle import source_plan

    saved, corpus, quality = source_plan(tmp_path)
    bundle = api.create_plan_bundle(saved, tmp_path / "bundle")
    report = api.study_plan(bundle, [scenario("same")])
    producer = {"corpus": corpus, "quality": quality}[role]
    before = producer.read_bytes()
    target = tmp_path / "producer-alias.json" if hardlink else producer
    if hardlink:
        target.hardlink_to(producer)
    dispatched = []
    monkeypatch.setattr(api.PlanArtifact, "save", lambda *args: dispatched.append(args))
    with pytest.raises(api.PlanError, match="cannot replace"):
        report.save(target)
    assert not dispatched and producer.read_bytes() == before


def test_foreign_producer_collision_is_not_interpreted_as_native(tmp_path, monkeypatch):
    """A re-signed path-flavor fixture, not proof of an actual foreign producer."""
    import hashlib
    from dataclasses import replace
    from pathlib import Path, PureWindowsPath

    from test_plan_bundle import source_plan

    saved, corpus, _ = source_plan(tmp_path)
    bundle = api.create_plan_bundle(saved, tmp_path / "bundle")
    data = json.loads(bundle._plan_bytes)
    native_windows = isinstance(Path(), PureWindowsPath)
    foreign = str(corpus).replace("\\", "/")[2:] if native_windows else "C:" + str(corpus)
    binding = data["result"]["replay_context"]["corpus"]["input"]
    binding.update(path=foreign, path_flavor="posix" if native_windows else "windows")
    data["fingerprint"] = api._digest({k: v for k, v in data.items() if k != "fingerprint"})
    raw = json.dumps(data).encode()
    manifest = json.loads(bundle._manifest_bytes)
    manifest["plan_fingerprint"] = data["fingerprint"]
    next(row for row in manifest["files"] if row["role"] == "plan").update(
        sha256=hashlib.sha256(raw).hexdigest(), size_bytes=len(raw)
    )
    held = replace(bundle, _plan_bytes=raw, _manifest_bytes=json.dumps(manifest).encode())
    report = api.study_plan(held, [scenario("same")])
    assert report.to_dict()["frozen_context"]["inputs"]["corpus"]["producer"]["path"] == foreign
    dispatched = []
    monkeypatch.setattr(api.PlanArtifact, "save", lambda *args: dispatched.append(args))
    report.save(corpus)
    assert dispatched


def test_unknown_native_metrics_remain_unknown(source, monkeypatch):
    original = service.enumerate_candidates

    def search(**kwargs):
        result = original(**kwargs)
        if result:
            result[0].ttft_ms = float("nan")
        return result

    monkeypatch.setattr(service, "enumerate_candidates", search)
    report = api.study_plan(source, [scenario("same")]).to_dict()
    delta = report["scenarios"][0]["comparison"]["matched"][0]["deltas"]["ttft_ms"]
    assert delta == {"before": None, "after": None, "delta": None, "unit": "ms", "state": "unknown"}


@pytest.mark.parametrize("invalid", ["context", "measured-claim", "native-unit", "lost-negative"])
def test_installed_consumer_checks_meaningful_receipt_semantics(source, invalid):
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "scripts" / "ci_plan_study.py"
    spec = importlib.util.spec_from_file_location("ci_plan_study_test", path)
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    report = api.study_plan(
        source,
        [scenario("same"), scenario("half-duty", duty_cycle=0.5), scenario("no-budget", budget=0)],
    ).to_dict()
    script.validate(report, source.to_dict())
    if invalid == "context":
        report["frozen_context"]["as_of_date"] = "2000-01-01"
    elif invalid == "measured-claim":
        report["performance"]["state"] = "measured"
    elif invalid == "native-unit":
        report["scenarios"][1]["comparison"]["matched"][0]["deltas"]["tokens_served_month"][
            "unit"
        ] = "requests/second"
    else:
        report["scenarios"][2]["trace"] = []
    with pytest.raises(AssertionError):
        script.validate(report, source.to_dict())


def test_installed_study_command_wiring_in_source_protocol_fixture(tmp_path, source, monkeypatch):
    """Exercise the consumer's commands; the patched origin guard is not installed proof."""
    import importlib.util
    import sys
    from pathlib import Path
    from types import SimpleNamespace

    root = Path(__file__).resolve().parents[1]
    path = root / "scripts" / "ci_plan_study.py"
    spec = importlib.util.spec_from_file_location("ci_plan_study_protocol_test", path)
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    origins = []

    def run_cli(arguments, cwd, env, expected_code=0):
        result = CliRunner().invoke(app, arguments)
        assert result.exit_code == expected_code, result.output
        return result.output

    monkeypatch.setitem(
        sys.modules,
        "ci_installed_acceptance",
        SimpleNamespace(
            assert_installed_origin=lambda origin, checkout: origins.append(origin),
            run_cli=run_cli,
        ),
    )
    saved = tmp_path / "plan.json"
    source.save(saved)
    bundle = api.create_plan_bundle(saved, tmp_path / "bundle")
    receipt = script.accept(tmp_path, {}, root, saved, bundle._directory)
    assert origins == [api.__file__]
    assert receipt["offline"] and len(receipt["receipts"]) == 2
    assert all(
        row["original_bytes_unchanged"] and row["infeasible_retained"]
        for row in receipt["receipts"]
    )
