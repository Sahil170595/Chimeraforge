"""Saved facts remain bound; fresh modeled comparisons never prove performance."""

import copy
from dataclasses import asdict, replace
import datetime as dt
import hashlib
import json

import pytest
from typer.testing import CliRunner

from chimeraforge.api import PlanRequest, artifact_from_dict, load_plan, plan
from chimeraforge.cli import app


def checked(saved, **kwargs):
    from chimeraforge.api import check_plan

    return check_plan(saved, **kwargs).to_dict()


def signed(data):
    body = {key: value for key, value in data.items() if key != "fingerprint"}
    data["fingerprint"] = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()
    return artifact_from_dict(data)


def quality(path, score=0.8):
    path.write_text(
        json.dumps({"results": {"mmlu": {"acc,none": score}}, "n-samples": {"mmlu": 5000}})
    )


def test_current_snapshot_roundtrip_check_and_immutability(tmp_path):
    saved = plan(PlanRequest(allow_network=False))
    before = saved.to_dict()
    assert before["schema_version"] == 2
    context = before["result"]["replay_context"]
    assert context["version"] == 1
    assert set(context["model_specs"]) == set(before["result"]["target_models"])
    assert context["hardware"]["raw"]["name"] == "RTX 4080 12GB"
    path = tmp_path / "plan.json"
    saved.save(path)
    raw = path.read_bytes()
    report = checked(load_plan(path))
    assert report["status"] == "unchanged" and report["exit_code"] == 0
    assert report["performance"]["state"] == "unverified"
    assert report["performance"]["required"] is False
    assert report["comparison"]["added"] == report["comparison"]["removed"] == []
    assert path.read_bytes() == raw and saved.to_dict() == before


def test_legacy_v1_is_loadable_and_reports_missing_binding(tmp_path):
    data = plan(PlanRequest(allow_network=False)).to_dict()
    data["schema_version"] = 1
    data["result"].pop("replay_context", None)
    legacy = signed(data)
    path = tmp_path / "legacy.json"
    legacy.save(path)
    report = checked(load_plan(path))
    assert report["exit_code"] == 1
    assert report["components"]["replay_context"]["state"] == "unverified"
    assert load_plan(path).to_dict() == legacy.to_dict()


def test_saved_network_permission_never_enables_check_network(monkeypatch):
    from chimeraforge.planner import resolver

    saved = plan(
        PlanRequest(
            models=["test/manual"],
            overrides={"params_b": 3, "n_layers": 28, "n_kv_heads": 8, "d_head": 128},
            allow_network=True,
        )
    )
    seen = []

    def inspect(ident, **kwargs):
        seen.append(kwargs["allow_network"])
        assert kwargs["allow_network"] is False
        return saved.spec(ident)

    monkeypatch.setattr(resolver, "resolve_spec", inspect)
    report = checked(saved)
    assert seen and seen == [False]
    assert report["exit_code"] == 0


@pytest.mark.parametrize("kind", ["moe", "hybrid", "mla"])
def test_full_saved_geometry_replays_without_cache_substitution(monkeypatch, kind):
    from chimeraforge.planner import resolver, service

    extra = {
        "moe": {"num_experts": 8, "experts_per_token": 2, "moe_intermediate_size": 1024},
        "hybrid": {"n_attention_layers": 4, "recurrent_state_bytes_per_seq": 1048576.0},
        "mla": {"kv_lora_rank": 512, "qk_rope_head_dim": 64},
    }[kind]
    spec = resolver.ModelSpec(
        "test/full", 3.0, 8, 8, 128, hidden_size=1024, source=resolver.SOURCE_HF, **extra
    )
    monkeypatch.setattr(service, "resolve_spec", lambda *args, **kwargs: spec)
    saved = plan(PlanRequest(models=[spec.name], allow_network=False, quality_target=0))
    other = replace(spec, source=resolver.SOURCE_REGISTRY_APPROX, params_b=8.0)
    monkeypatch.setattr(resolver, "resolve_spec", lambda *args, **kwargs: other)
    original = service.enumerate_candidates
    consumed = []

    def search(**kwargs):
        consumed.append(asdict(kwargs["specs"][spec.name]))
        return original(**kwargs)

    monkeypatch.setattr(service, "enumerate_candidates", search)
    report = checked(saved)
    assert consumed == [asdict(spec)]
    assert report["resolution_view"][spec.name]["state"] == "unverified"
    assert report["components"]["replay_context"]["state"] == "unchanged"
    assert report["exit_code"] == 0


def test_changed_local_resolution_provenance_is_explicit_but_not_substituted(monkeypatch):
    from chimeraforge.planner import resolver, service

    spec = resolver.ModelSpec("test/full", 3.0, 8, 8, 128, source=resolver.SOURCE_HF)
    monkeypatch.setattr(service, "resolve_spec", lambda *args, **kwargs: spec)
    saved = plan(PlanRequest(models=[spec.name], allow_network=False, quality_target=0))
    monkeypatch.setattr(
        resolver,
        "resolve_spec",
        lambda *args, **kwargs: replace(spec, source=resolver.SOURCE_OLLAMA),
    )
    report = checked(saved)
    assert report["resolution_view"][spec.name]["state"] == "changed"
    assert (
        report["resolution_view"][spec.name]["before"]["source"]
        != report["resolution_view"][spec.name]["after"]["source"]
    )
    assert report["comparison"]["added"] == report["comparison"]["removed"] == []
    assert report["exit_code"] == 1


def test_auto_unified_hardware_pins_original_host_and_applies_fraction_once(monkeypatch):
    from chimeraforge.planner import engine, hardware, service

    gpu = hardware.GPUSpec(
        "Pinned unified",
        64.0,
        400.0,
        0.01,
        fp16_tflops=20.0,
        vendor="apple",
        unified_memory=True,
        memory_options_gb=(64,),
    )
    monkeypatch.setitem(hardware.GPU_DB, gpu.name, gpu)
    monkeypatch.setattr(engine, "resolve_hardware", lambda *args: (gpu, []))
    monkeypatch.setattr(service, "local_plan_platform", lambda: "macos")
    saved = plan(PlanRequest(hardware="auto", unified_memory_fraction=0.5, allow_network=False))
    context = saved.to_dict()["result"]["replay_context"]
    assert context["hardware"]["raw"]["vram_gb"] == 64
    assert context["hardware"]["effective"]["vram_gb"] == 32

    def forbidden(*args):
        raise AssertionError("recheck must not probe a new host")

    monkeypatch.setattr(engine, "resolve_hardware", forbidden)
    monkeypatch.setattr(service, "local_plan_platform", forbidden)
    assert checked(saved)["exit_code"] == 0


def test_relative_quality_uses_original_absolute_input_not_namesake(monkeypatch, tmp_path):
    original = tmp_path / "original"
    other = tmp_path / "other"
    original.mkdir()
    other.mkdir()
    quality(original / "quality.json")
    quality(other / "quality.json", 0.01)
    monkeypatch.chdir(original)
    saved = plan(PlanRequest(quality_from="quality.json", allow_network=False))
    before = saved.to_dict()
    monkeypatch.chdir(other)
    assert checked(saved)["exit_code"] == 0
    assert saved.to_dict() == before
    quality(original / "quality.json", 0.01)
    report = checked(saved)
    assert report["components"]["quality"]["state"] == "changed"
    assert report["comparison"]["feasibility"] == "lost"
    assert report["comparison"]["removed"] and report["exit_code"] == 1


def test_missing_original_quality_file_is_unverified_not_namesake(monkeypatch, tmp_path):
    quality(tmp_path / "quality.json")
    monkeypatch.chdir(tmp_path)
    saved = plan(PlanRequest(quality_from="quality.json", allow_network=False))
    (tmp_path / "quality.json").unlink()
    report = checked(saved)
    assert report["exit_code"] == 1
    assert report["components"]["quality"]["state"] == "unverified"
    assert report["comparison"] is None


def test_noncloud_price_change_is_actionable_and_repriced_once(monkeypatch):
    from chimeraforge.planner import hardware

    saved = plan(PlanRequest(budget=10000, gpu_price_multiplier=2, allow_network=False))
    gpu = hardware.GPU_DB["RTX 4080 12GB"]
    monkeypatch.setitem(
        hardware.GPU_DB, gpu.name, replace(gpu, cost_per_hour=gpu.cost_per_hour * 2)
    )
    report = checked(saved)
    assert report["components"]["price"]["state"] == "changed"
    common = report["comparison"]["matched"]
    assert common and all(
        row["deltas"]["monthly_cost"]["after"]
        == pytest.approx(row["deltas"]["monthly_cost"]["before"] * 2)
        for row in common
    )
    assert report["exit_code"] == 1


def test_unknown_predictions_remain_unknown_in_deltas():
    saved = plan(
        PlanRequest(gpu_overrides={"cost_per_hour": 0.0}, budget=10000, allow_network=False)
    )
    report = checked(saved)
    assert report["exit_code"] == 0
    for row in report["comparison"]["matched"]:
        cost = row["deltas"]["monthly_cost"]
        assert cost["before"] is cost["after"] is cost["delta"] is None
        assert cost["state"] == "unknown"


@pytest.mark.parametrize("age, state, exit_code", [(90, "unchanged", 0), (91, "expired", 1)])
def test_cloud_existing_expiry_boundary(monkeypatch, age, state, exit_code):
    from chimeraforge.planner import cloudprice

    captured = dt.date.fromisoformat(cloudprice.load_cloud_prices()["captured_at"])
    monkeypatch.setattr(cloudprice, "_today", lambda: captured)
    saved = plan(PlanRequest(hardware="H100 80GB", cloud="aws", budget=100000, allow_network=False))
    monkeypatch.setattr(cloudprice, "_today", lambda: captured + dt.timedelta(days=age))
    report = checked(saved)
    assert report["components"]["cloud"]["state"] == state
    assert report["exit_code"] == exit_code


def test_cloud_is_not_read_or_expired_for_noncloud_plan(monkeypatch):
    from chimeraforge.planner import engine

    saved = plan(PlanRequest(allow_network=False))

    def forbidden():
        raise AssertionError("a non-cloud plan does not consume cloud prices")

    monkeypatch.setattr(engine, "load_cloud_prices", forbidden)
    assert checked(saved)["components"]["cloud"]["state"] == "not_used"


def test_corpus_and_tool_changes_are_separate_from_performance(monkeypatch):
    from chimeraforge.planner import service
    import chimeraforge.api as api

    saved = plan(PlanRequest(allow_network=False))
    original = service.load_effective_models

    def changed():
        corpus = copy.deepcopy(original())
        corpus.throughput.lookup = {
            key: value * 0.8 for key, value in corpus.throughput.lookup.items()
        }
        return corpus

    monkeypatch.setattr(service, "load_effective_models", changed)
    monkeypatch.setattr(api, "__version__", "0.51.1")
    report = checked(saved)
    assert report["components"]["corpus"]["state"] == "changed"
    assert report["components"]["tool"]["state"] == "changed"
    assert report["performance"]["state"] == "unverified" and report["exit_code"] == 1


@pytest.mark.parametrize("invalid", ["missing", "malformed"])
def test_check_cli_malformed_input_exit_two(tmp_path, invalid):
    path = tmp_path / "plan.json"
    if invalid == "malformed":
        path.write_text('{"schema_version":2}')
    result = CliRunner().invoke(app, ["check", str(path), "--json"])
    assert result.exit_code == 2
    assert json.loads(result.stdout)["error"]


def test_check_cli_success(tmp_path):
    path = tmp_path / "plan.json"
    plan(PlanRequest(allow_network=False)).save(path)
    result = CliRunner().invoke(app, ["check", str(path), "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["status"] == "unchanged"


def corpus_bytes():
    from importlib import resources

    return resources.files("chimeraforge.planner.data").joinpath("fitted_models.json").read_bytes()


def test_relative_corpus_original_path_changed_bytes_and_missing(monkeypatch, tmp_path):
    original = tmp_path / "original"
    namesake = tmp_path / "namesake"
    original.mkdir()
    namesake.mkdir()
    source = original / "corpus.json"
    source.write_bytes(corpus_bytes())
    (namesake / "corpus.json").write_text("{}")
    monkeypatch.chdir(original)
    saved = plan(PlanRequest(models_path="corpus.json", allow_network=False))
    monkeypatch.chdir(namesake)
    assert checked(saved)["exit_code"] == 0
    source.write_bytes(source.read_bytes() + b"\n")
    report = checked(saved)
    assert report["components"]["corpus"]["state"] == "changed"
    assert report["comparison"]["changed"] is False
    source.unlink()
    report = checked(saved)
    assert report["components"]["corpus"]["state"] == "unverified"
    assert report["comparison"] is None and report["exit_code"] == 1


@pytest.mark.parametrize("source", ["corpus", "quality"])
def test_snapshot_hashes_parsed_bytes_without_second_read(monkeypatch, tmp_path, source):
    from pathlib import Path

    path = tmp_path / f"{source}.json"
    if source == "corpus":
        path.write_bytes(corpus_bytes())
    else:
        quality(path)
    consumed = path.read_bytes()
    original = Path.read_bytes
    reads = []

    def read_once(p):
        raw = original(p)
        if p.resolve() == path:
            reads.append(raw)
            assert len(reads) == 1, "the receipt must use bytes consumed by the parser"
            p.write_bytes(raw + b"\n")
        return raw

    monkeypatch.setattr(Path, "read_bytes", read_once)
    options = {"models_path" if source == "corpus" else "quality_from": str(path)}
    saved = plan(PlanRequest(**options, allow_network=False))
    binding = saved.to_dict()["result"]["replay_context"][source]["input"]
    assert binding["sha256"] == hashlib.sha256(consumed).hexdigest()
    assert reads == [consumed]


def test_cloud_capture_and_search_consume_one_cached_object(monkeypatch):
    from chimeraforge.planner import cloudprice, engine

    snapshot = copy.deepcopy(cloudprice.load_cloud_prices())
    calls = []

    def consume():
        calls.append(True)
        assert len(calls) == 1
        return snapshot

    monkeypatch.setattr(engine, "load_cloud_prices", consume)
    saved = plan(PlanRequest(hardware="H100 80GB", cloud="aws", budget=100000, allow_network=False))
    bound = saved.to_dict()["result"]["replay_context"]["cloud"]
    assert calls == [True]
    assert bound["captured_at"] == snapshot["captured_at"]
    assert bound["offers"] and all(row["gpu"] == "H100 80GB" for row in bound["offers"])


@pytest.mark.parametrize(
    "damage", ["version", "fraction", "model", "corpus", "quality", "contribution", "grid"]
)
def test_resigned_malformed_context_is_rejected(tmp_path, damage):
    from chimeraforge.api import PlanError

    path = tmp_path / "quality.json"
    quality(path)
    data = plan(PlanRequest(quality_from=str(path), allow_network=False)).to_dict()
    context = data["result"]["replay_context"]
    if damage == "version":
        context["version"] = True
    elif damage == "fraction":
        context["hardware"]["effective"]["vram_gb"] *= 0.5
    elif damage == "model":
        context["model_specs"].pop(next(iter(context["model_specs"])))
    elif damage == "corpus":
        context["corpus"]["input"] = []
    elif damage == "quality":
        context["quality"]["aggregate"]["score"] = 0.99
    elif damage == "contribution":
        context["contributions"]["used_ids"] = ["unsigned-not-consumed"]
    elif damage == "grid":
        context["grid"] = {"trust": "measured"}
    with pytest.raises(PlanError):
        signed(data)


def test_contribution_membership_and_unsigned_provenance_are_bound(monkeypatch):
    from chimeraforge import contrib
    from chimeraforge.planner import engine
    from test_contributions import bench_result

    row = contrib.build_contribution(bench_result())
    monkeypatch.setattr(engine, "load_quarantine", lambda: [row])
    saved = plan(
        PlanRequest(
            hardware="RTX 4090 24GB", use_contributions=True, budget=10000, allow_network=False
        )
    )
    binding = saved.to_dict()["result"]["replay_context"]["contributions"]
    assert [record["id"] for record in binding["records"]] == [row["id"]]
    assert binding["used_ids"] == [row["id"]]
    assert "unsigned" in binding["trust"]
    assert checked(saved)["exit_code"] == 0
    monkeypatch.setattr(engine, "load_quarantine", lambda: [])
    report = checked(saved)
    assert report["components"]["contributions"]["state"] == "changed"
    assert report["exit_code"] == 1


def test_recommendation_order_identity_and_native_deltas(monkeypatch):
    from chimeraforge.planner import service

    saved = plan(PlanRequest(allow_network=False))
    assert len(saved.to_dict()["result"]["candidates"]) > 2
    search = service.enumerate_candidates

    def changed(**kwargs):
        rows = search(**kwargs)
        rows[0] = replace(rows[0], total_throughput_tps=rows[0].total_throughput_tps + 10)
        return list(reversed(rows))

    monkeypatch.setattr(service, "enumerate_candidates", changed)
    report = checked(saved)
    comparison = report["comparison"]
    assert report["exit_code"] == 1 and comparison["ordering_changed"]
    assert comparison["recommendation_before"] != comparison["recommendation_after"]
    assert set(comparison["recommendation_before"]) == {
        "model",
        "quant",
        "backend",
        "tensor_parallel",
        "pipeline_parallel",
        "n_agents",
        "mode",
        "platform",
    }
    assert comparison["matched"][0]["deltas"]["total_throughput_tps"] == {
        "before": saved.candidate().total_throughput_tps,
        "after": saved.candidate().total_throughput_tps + 10,
        "delta": 10,
        "unit": "tokens/second",
        "state": "changed",
    }


def test_feasibility_gained_and_empty_unchanged(tmp_path):
    path = tmp_path / "quality.json"
    quality(path, 0.01)
    saved = plan(PlanRequest(quality_from=str(path), allow_network=False))
    report = checked(saved)
    assert report["exit_code"] == 0
    assert report["comparison"]["feasibility"] == "unchanged"
    assert report["comparison"]["recommendation_before"] is None
    quality(path, 0.8)
    report = checked(saved)
    assert report["comparison"]["feasibility"] == "gained"
    assert report["comparison"]["added"] and report["exit_code"] == 1
    assert report["comparison"]["trace_before"]


@pytest.mark.parametrize(
    "flavor,path", [("posix", "/home/runner/models.json"), ("windows", r"C:\models\corpus.json")]
)
def test_portable_absolute_input_syntax_loads(flavor, path):
    data = plan(PlanRequest(allow_network=False)).to_dict()
    receipt = {"kind": "file", "path": path, "path_flavor": flavor, "sha256": "a" * 64}
    data["result"]["replay_context"]["corpus"]["input"] = receipt
    assert signed(data).to_dict()["result"]["replay_context"]["corpus"]["input"] == receipt
    receipt.pop("path_flavor")
    assert signed(data).to_dict()["result"]["replay_context"]["corpus"]["input"] == receipt


@pytest.mark.parametrize("source", ["corpus", "quality"])
def test_foreign_absolute_input_is_unverified_despite_native_namesake(
    monkeypatch, tmp_path, source
):
    from pathlib import Path, PureWindowsPath
    from chimeraforge.planner import service

    path = tmp_path / "input.json"
    if source == "corpus":
        path.write_bytes(corpus_bytes())
    else:
        quality(path)
    options = {"models_path" if source == "corpus" else "quality_from": str(path)}
    data = plan(PlanRequest(**options, allow_network=False)).to_dict()
    native_windows = isinstance(Path(), PureWindowsPath)
    flavor = "posix" if native_windows else "windows"
    foreign = path.as_posix().split(":", 1)[-1] if native_windows else r"C:\models\input.json"
    monkeypatch.chdir(tmp_path)
    namesake = Path(foreign)
    if not native_windows:
        namesake.write_bytes(path.read_bytes())
    assert namesake.is_file(), "native coercion would wrongly accept this namesake"
    binding = data["result"]["replay_context"][source]
    binding["input"]["path"] = foreign
    binding["input"]["path_flavor"] = flavor
    if source == "quality":
        binding["aggregate"]["source"] = foreign
        for cell in binding["scores"]["cells"].values():
            cell["source"] = foreign
    artifact = signed(data)

    def forbidden(*args, **kwargs):
        raise AssertionError("a foreign source cannot be consumed via a native namesake")

    monkeypatch.setattr(
        service, "load_models" if source == "corpus" else "load_quality_file", forbidden
    )
    report = checked(artifact)
    assert report["exit_code"] == 1 and report["comparison"] is None
    assert report["components"][source]["state"] == "unverified"


def legacy_from_current(artifact):
    data = artifact.to_dict()
    data["schema_version"] = 1
    data["result"].pop("replay_context")
    return signed(data)


@pytest.mark.parametrize("source", ["corpus", "quality"])
def test_context_v1_implicit_path_flavor_remains_comparable(tmp_path, source):
    path = tmp_path / "input.json"
    if source == "corpus":
        path.write_bytes(corpus_bytes())
    else:
        quality(path)
    option = "models_path" if source == "corpus" else "quality_from"
    data = plan(PlanRequest(**{option: str(path)}, allow_network=False)).to_dict()
    data["result"]["replay_context"][source]["input"].pop("path_flavor")
    assert checked(signed(data))["exit_code"] == 0


def test_unchanged_reference_gpu_keeps_own_measurement_over_quarantine(monkeypatch):
    from chimeraforge import contrib
    from chimeraforge.planner import engine
    from chimeraforge.planner.hardware import REFERENCE_GPU
    from test_contributions import bench_result

    bench = bench_result(gpu="NVIDIA GeForce RTX 4080 Laptop GPU")
    bench["environment"]["gpu_memory_gb"] = 12
    row = contrib.build_contribution(bench)
    monkeypatch.setattr(engine, "load_quarantine", lambda: [row])
    saved = plan(
        PlanRequest(
            models=["llama3.2-3b"],
            hardware=REFERENCE_GPU,
            use_contributions=True,
            allow_network=False,
            quality_target=0,
            budget=1e9,
        )
    )
    own = next(
        row
        for row in saved.to_dict()["result"]["candidates"]
        if row["quant"] == "FP16" and row["backend"] == "vllm"
    )
    assert own["throughput_tps"] == 57.2
    assert saved.to_dict()["result"]["replay_context"]["contributions"]["used_ids"] == []
    report = checked(saved)
    assert report["exit_code"] == 0
    assert report["components"]["contributions"]["state"] == "unchanged"
    assert all(
        row["deltas"]["throughput_tps"]["state"] == "unchanged"
        for row in report["comparison"]["matched"]
    )


def test_legacy_reports_known_changed_effective_corpus_without_replay(monkeypatch):
    from chimeraforge.planner import service

    legacy = legacy_from_current(plan(PlanRequest(allow_network=False)))
    original = service.load_effective_models

    def changed():
        corpus = copy.deepcopy(original())
        corpus.throughput.lookup = {
            key: value * 0.8 for key, value in corpus.throughput.lookup.items()
        }
        return corpus

    monkeypatch.setattr(service, "load_effective_models", changed)
    report = checked(legacy)
    assert report["components"]["corpus"]["state"] == "changed"
    assert report["components"]["replay_context"]["state"] == "unverified"
    assert report["comparison"] is None and report["exit_code"] == 1


def test_legacy_current_cloud_expiry_is_known_but_history_unverified(monkeypatch):
    from chimeraforge.planner import cloudprice

    captured = dt.date.fromisoformat(cloudprice.load_cloud_prices()["captured_at"])
    monkeypatch.setattr(cloudprice, "_today", lambda: captured)
    legacy = legacy_from_current(
        plan(PlanRequest(hardware="H100 80GB", cloud="aws", budget=100000, allow_network=False))
    )
    monkeypatch.setattr(cloudprice, "_today", lambda: captured + dt.timedelta(days=91))
    report = checked(legacy)
    assert report["components"]["cloud"]["state"] == "expired"
    assert report["components"]["cloud"]["age_days"] == 91
    assert report["components"]["cloud"]["before"] is None
    assert report["components"]["replay_context"]["state"] == "unverified"
    assert report["exit_code"] == 1


def test_legacy_does_not_resolve_relative_external_inputs_or_probe_auto(monkeypatch, tmp_path):
    from chimeraforge.planner import engine, service

    data = legacy_from_current(plan(PlanRequest(allow_network=False))).to_dict()
    data["inputs"].update(hardware="auto", models_path="corpus.json", quality_from="quality.json")
    (tmp_path / "corpus.json").write_bytes(corpus_bytes())
    quality(tmp_path / "quality.json")
    monkeypatch.chdir(tmp_path)

    def forbidden(*args, **kwargs):
        raise AssertionError("legacy missing receipts never authorize source or host substitution")

    monkeypatch.setattr(service, "load_models", forbidden)
    monkeypatch.setattr(service, "load_quality_file", forbidden)
    monkeypatch.setattr(service, "local_plan_platform", forbidden)
    monkeypatch.setattr(engine, "resolve_hardware", forbidden)
    report = checked(signed(data))
    assert report["components"]["corpus"]["state"] == "unverified"
    assert report["components"]["quality"]["state"] == "unverified"
    assert report["components"]["cloud"]["state"] == "not_used"
    assert report["exit_code"] == 1 and report["comparison"] is None
