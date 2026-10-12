"""Frozen prediction scoring is conditional arithmetic, never physical authentication."""

import copy
from dataclasses import asdict
import json
import math
import os

import pytest
from typer.testing import CliRunner

from chimeraforge import api
from chimeraforge.bench.metrics import RunMetrics, aggregate_runs
from chimeraforge.plan_check import identity
from chimeraforge.planner.replay import digest


def seal(data):
    data["fingerprint"] = digest({k: v for k, v in data.items() if k != "fingerprint"})
    return data


@pytest.fixture
def frozen(monkeypatch):
    from chimeraforge.planner.resolver import spec_from_hf

    spec = spec_from_hf(
        "org/model",
        {
            "num_hidden_layers": 28,
            "num_attention_heads": 24,
            "num_key_value_heads": 8,
            "hidden_size": 3072,
            "vocab_size": 128256,
        },
        3.21,
    )
    monkeypatch.setattr("chimeraforge.planner.service.resolve_spec", lambda *a, **k: spec)
    data = api.plan(
        api.PlanRequest(
            models=["org/model"],
            allow_network=False,
            platform="windows",
            quality_target=0,
            budget=100000,
            avg_tokens=4,
            prompt_tokens=8,
        )
    ).to_dict()
    # Explicitly synthetic prediction oracle; not a measured fitted coefficient.
    data["result"]["candidates"][0]["throughput_tps"] = 40.0
    return api.artifact_from_dict(seal(data))


def policy(saved, **changes):
    return {
        "plan_fingerprint": saved.to_dict()["fingerprint"],
        "candidate_indices": [0],
        "expected_receipts_per_index": {"0": 1},
        "relative_error_band": 0.25,
        **changes,
    }


def native(saved, durations=(125.0, 125.0, 125.0), serial=0):
    """Synthetic native envelope with declared capability-shaped serving metadata."""
    data = saved.to_dict()
    candidate = data["result"]["candidates"][0]
    context = data["result"]["replay_context"]
    samples = [
        RunMetrics(4, 4000 / ms, 2, 2 + ms, 2, ms, 8, 0, "server-prefill-duration")
        for ms in durations
    ]
    serving = {
        "backend": "ollama",
        "version": "synthetic-protocol",
        "model": candidate["model"],
        "model_digest": "a" * 64,
        "quant": candidate["quant"],
        "context_length": 2048,
        "device": "gpu",
        "tensor_parallel": 1,
        "pipeline_parallel": 1,
        "replicas": candidate["n_agents"],
        "hardware": context["hardware"]["effective"],
        "model_spec": context["model_specs"][candidate["model"]],
        "prefix_cache": False,
        "source": "synthetic capability-shaped metadata",
    }
    measurement = {
        "model": candidate["model"],
        "backend": "ollama",
        "quant": None,
        "workload": "single",
        "runs": len(samples),
        "context_length": 2048,
        "individual_runs": [asdict(r) for r in samples],
        "aggregate": asdict(aggregate_runs(samples)),
        "environment": {},
        "warnings": [],
        "timestamp": str(serial),
    }
    return seal(
        {
            "schema_version": 1,
            "kind": "chimeraforge.plan-benchmark",
            "created_at": str(serial),
            "plan": {
                "fingerprint": data["fingerprint"],
                "candidate_index": 0,
                "identity": identity(candidate),
                "served_model": candidate["model"],
            },
            "measurement": measurement,
            "execution": {
                "request": {
                    "prompt_sha256": "b" * 64,
                    "prompt_characters": 5,
                    "options": {"num_predict": 4, "num_ctx": 2048},
                    "workload": "single",
                    "concurrency": 1,
                    "arrival_rate": None,
                    "requested_count": len(samples),
                },
                "serving_before": copy.deepcopy(serving),
                "serving_after": copy.deepcopy(serving),
                "requested_count": len(samples),
                "successful_count": len(samples),
                "failed_count": 0,
                "elapsed_seconds": 1.0,
                "individual_runs": measurement["individual_runs"],
            },
            "binding": {},
            "audit": {},
            "status": "completed",
            "configuration_status": "unverified",
            "exit_code": 0,
            "limits": "Synthetic protocol only",
        }
    )


def score(saved, receipts, chosen=None):
    return api.score_predictions(saved, receipts, policy=chosen or policy(saved)).to_dict()


def refresh(row):
    row["measurement"]["aggregate"] = asdict(
        aggregate_runs([RunMetrics(**sample) for sample in row["measurement"]["individual_runs"]])
    )
    return seal(row)


def test_frozen_predictions_mean_native_rates_boundary_and_no_replanning(frozen, monkeypatch):
    for target in (
        "chimeraforge.api.run_plan",
        "chimeraforge.planner.service.run_plan",
        "chimeraforge.api.plan",
        "chimeraforge.api.check_plan",
        "chimeraforge.planner.models.load_models",
        "chimeraforge.plan_bundle.check",
    ):
        monkeypatch.setattr(target, lambda *a, **k: pytest.fail("scoring replanned/current corpus"))
    receipt = native(frozen)
    result = api.score_predictions(
        frozen, [receipt], policy=api.PredictionScorePolicy(**policy(frozen))
    )
    report = result.to_dict()
    assert result.exit_code == report["exit_code"] == 0
    row = report["rows"][0]
    assert row["predicted"] == 40 and row["measured"] == 32 and row["relative_error"] == 0.25
    assert row["candidate_digest"] == digest(frozen.to_dict()["result"]["candidates"][0])
    assert report["assurance"]["source_authentication"] == "unverified"
    report["rows"].clear()
    report["exit_code"] = 99
    assert result.to_dict()["rows"] and result.exit_code == 0
    mean = score(frozen, [native(frozen, (100, 200, 50))])
    assert mean["rows"][0]["measured"] == pytest.approx(140 / 3)
    assert mean["rows"][0]["relative_error"] == pytest.approx(-1 / 7)


def test_breach_survives_missing_and_extra_population(frozen):
    row = native(frozen, (200, 200, 200))
    chosen = policy(frozen, candidate_indices=[0, 1], expected_receipts_per_index={"0": 2, "1": 1})
    report = score(frozen, [row], chosen)
    assert report["exit_code"] == 1 and len(report["coverage"]) == 2
    assert report["coverage"][0]["missing"] == 1 and report["coverage"][1]["missing"] == 1
    assert report["worst_rows"] == [0]
    empty = score(frozen, [])
    assert empty["exit_code"] == 3 and empty["coverage"][0]["missing"] == 1
    extra = score(frozen, [native(frozen), native(frozen, (100, 100, 100))])
    assert extra["exit_code"] == 3 and len(extra["rows"]) == 2


@pytest.mark.parametrize(
    "change",
    [
        "plan",
        "index",
        "identity",
        "cpu",
        "hardware",
        "geometry",
        "length",
        "cache",
        "wrapper",
        "modifiers",
        "basis",
        "failed",
    ],
)
def test_ineligible_keeps_measurement_without_error(frozen, change):
    receipt = native(frozen)
    if change == "plan":
        receipt["plan"]["fingerprint"] = "c" * 64
    elif change == "index":
        receipt["plan"]["candidate_index"] = 999999
    elif change == "identity":
        receipt["plan"]["identity"]["quant"] = "wrong"
    elif change in ("cpu", "hardware", "geometry", "wrapper"):
        for phase in ("serving_before", "serving_after"):
            observation = receipt["execution"][phase]
            if change == "cpu":
                observation["device"] = "cpu"
                receipt["measurement"]["environment"] = {"gpu": "RTX 4080 12GB"}
            elif change == "hardware":
                observation["hardware"] = {"name": "RTX 4080 12GB"}
            elif change == "geometry":
                observation["model_spec"]["hidden_size"] = None
            else:
                observation["backend"] = "llama.cpp"
    elif change in ("length", "cache", "basis"):
        for sample in receipt["measurement"]["individual_runs"]:
            sample[
                {"length": "prompt_tokens", "cache": "cached_prompt_tokens", "basis": "ttft_basis"}[
                    change
                ]
            ] = "client-stream-first-content" if change == "basis" else 1
        refresh(receipt)
    elif change == "modifiers":
        changed = frozen.to_dict()
        changed["result"]["candidates"][0]["lora_adapters"] = 1
        frozen = api.artifact_from_dict(seal(changed))
        receipt["plan"]["fingerprint"] = frozen.to_dict()["fingerprint"]
    else:
        receipt["execution"].update(requested_count=4, failed_count=1)
        receipt["execution"]["request"]["requested_count"] = receipt["measurement"]["runs"] = 4
    report = score(frozen, [seal(receipt)])
    assert report["exit_code"] == 3 and report["rows"][0]["relative_error"] is None
    assert report["rows"][0]["state"] in ("binding_mismatch", "unavailable", "extra")


def test_producer_audit_is_ignored_but_resealed_bad_arithmetic_is_malformed(frozen):
    row = native(frozen)
    row.update(binding={"private": "forged pass"}, audit={"arbitrary": "forged pass"})
    assert score(frozen, [seal(row)])["exit_code"] == 0
    row["measurement"]["aggregate"]["throughput_tps"]["mean"] = 999
    with pytest.raises(api.PlanError):
        score(frozen, [seal(row)])


def test_duplicate_semantics_ignore_labels_and_normalize_real_facts(frozen):
    first, second = native(frozen), native(frozen, serial=98)
    second["measurement"]["environment"] = {"gpu": "forged-client-gpu"}
    for phase in ("serving_before", "serving_after"):
        observation = second["execution"][phase]
        observation["captured_at"] = "different"
        observation["source"] = "different"
        observation["hardware"]["vram_gb"] = int(observation["hardware"]["vram_gb"])
    report = score(
        frozen, [first, seal(second)], policy(frozen, expected_receipts_per_index={"0": 2})
    )
    assert report["exit_code"] == 3
    assert all(
        row["state"] == "duplicate" and row["relative_error"] is None for row in report["rows"]
    )
    assert all(row["measured"] == 32 for row in report["rows"])


@pytest.mark.parametrize(
    "field,value",
    [
        ("num_experts", False),
        ("experts_per_token", False),
        ("parallel_hybrid", 0),
        ("n_layers", True),
    ],
)
def test_wrong_type_geometry_never_aliases_known_absence(frozen, field, value):
    receipt = native(frozen)
    for phase in ("serving_before", "serving_after"):
        receipt["execution"][phase]["model_spec"][field] = value
    report = score(frozen, [seal(receipt)])
    assert report["exit_code"] == 3 and report["rows"][0]["relative_error"] is None


@pytest.mark.parametrize("device", ["unknown", "accelerator", "cuda", None])
def test_gpu_placement_must_be_known_not_merely_stable(frozen, device):
    receipt = native(frozen)
    for phase in ("serving_before", "serving_after"):
        receipt["execution"][phase]["device"] = device
    report = score(frozen, [seal(receipt)])
    assert report["exit_code"] == 3 and report["rows"][0]["relative_error"] is None
    assert report["rows"][0]["measured"] == 32


def test_unique_breach_survives_whole_duplicate_group(frozen):
    report = score(
        frozen,
        [native(frozen), native(frozen, serial=2), native(frozen, (200, 200, 200))],
        policy(frozen, expected_receipts_per_index={"0": 3}),
    )
    assert report["exit_code"] == 1 and report["worst_rows"] == [2]
    assert [row["state"] for row in report["rows"]] == ["duplicate", "duplicate", "breach"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("tensor_parallel", 2),
        ("pipeline_parallel", 2),
        ("offload_fraction", 0.1),
        ("prefix_cache_hit_rate", 0.1),
        ("backend", "llama.cpp"),
    ],
)
def test_saved_modifiers_parallelism_and_wrapper_do_not_upgrade_base_comparator(
    frozen, field, value
):
    data = frozen.to_dict()
    data["result"]["candidates"][0][field] = value
    saved = api.artifact_from_dict(seal(data))
    report = score(saved, [native(saved)])
    assert report["exit_code"] == 3 and report["rows"][0]["relative_error"] is None


def test_explicit_model_tag_does_not_accept_appended_latest(frozen):
    data = frozen.to_dict()
    old, new = "org/model", "org/model:Q4"
    data["result"]["target_models"] = [new]
    data["inputs"]["models"] = [new]
    for row in data["result"]["candidates"]:
        row["model"] = new
    for mapping in (data["result"]["specs"], data["result"]["replay_context"]["model_specs"]):
        mapping[new] = dict(mapping.pop(old), name=new)
    saved = api.artifact_from_dict(seal(data))
    receipt = native(saved)
    for phase in ("serving_before", "serving_after"):
        receipt["execution"][phase]["model"] = new + ":latest"
    report = score(saved, [seal(receipt)])
    assert report["exit_code"] == 3 and report["rows"][0]["state"] == "binding_mismatch"


def test_source_private_values_never_enter_public_projection(frozen):
    receipt = native(frozen)
    receipt["execution"]["request"]["options"]["private"] = (
        "https://u:private-token@host/?secret=private-token"
    )
    receipt["measurement"]["warnings"] = ["private-token"]
    receipt["binding"] = receipt["audit"] = {"private-token": "private-token"}
    for phase in ("serving_before", "serving_after"):
        receipt["execution"][phase]["source"] = "private-token"
        receipt["execution"][phase]["hardware"]["source_url"] = "private-token"
    report = score(frozen, [seal(receipt)])
    assert report["exit_code"] == 0 and "private-token" not in json.dumps(report)


def test_bundle_held_bytes_survive_file_changes_and_protect_every_member(
    frozen, tmp_path, monkeypatch
):
    path = tmp_path / "plan.json"
    frozen.save(path)
    bundle = api.create_plan_bundle(path, tmp_path / "bundle")
    receipt = native(frozen)
    report = api.score_predictions(bundle, [receipt], policy=policy(frozen))
    assert report.to_dict()["inputs"]["plan"]["producing_bytes"] == "verified_content"
    assert score(bundle._directory, [receipt], policy(frozen))["exit_code"] == 0
    for member in bundle._directory.iterdir():
        with pytest.raises(api.PlanError):
            report.save(member)
    (bundle._directory / "corpus.json").write_text("private-token")
    monkeypatch.setattr(
        "chimeraforge.plan_bundle.check", lambda *a, **k: pytest.fail("bundle replanned")
    )
    assert score(frozen, [receipt])["exit_code"] == 0
    assert (
        api.score_predictions(bundle, [receipt], policy=policy(frozen)).to_dict()["exit_code"] == 0
    )
    with pytest.raises(api.PlanError):
        api.score_predictions(bundle._directory, [receipt], policy=policy(frozen))


def test_cached_paths_read_once_but_each_declared_occurrence_is_budgeted(
    frozen, tmp_path, monkeypatch
):
    import chimeraforge.prediction_score as module

    receipt = tmp_path / "bench.json"
    raw = json.dumps(native(frozen)).encode()
    receipt.write_bytes(raw)
    chosen = policy(frozen, expected_receipts_per_index={"0": 2})
    full = score(frozen, [receipt, receipt], chosen)
    original = module._read
    calls = []

    def read(path, limit, **kwargs):
        calls.append(path)
        return original(path, limit, **kwargs)

    monkeypatch.setattr(module, "_read", read)
    assert (
        score(frozen, [receipt, receipt], chosen)["inputs"]["total_bytes"]
        == full["inputs"]["total_bytes"]
    )
    assert calls == [receipt]
    monkeypatch.setattr(module, "MAX_TOTAL_BYTES", full["inputs"]["total_bytes"] - 1)
    with pytest.raises(api.PlanError):
        score(frozen, [receipt, receipt], chosen)


def test_boundary_above_band_and_finite_error_required(frozen):
    data = frozen.to_dict()
    data["result"]["candidates"][0]["throughput_tps"] = math.nextafter(40, math.inf)
    saved = api.artifact_from_dict(seal(data))
    assert score(saved, [native(saved)])["exit_code"] == 1
    data["result"]["candidates"][0]["throughput_tps"] = 1e308
    saved = api.artifact_from_dict(seal(data))
    report = score(saved, [native(saved, (1e303, 1e303, 1e303))])
    assert report["exit_code"] == 3 and report["rows"][0]["relative_error"] is None


@pytest.mark.parametrize(
    "field",
    ["plan_fingerprint", "candidate_indices", "expected_receipts_per_index", "relative_error_band"],
)
def test_policy_fields_cannot_be_defaulted(frozen, field):
    chosen = policy(frozen)
    chosen.pop(field)
    with pytest.raises(api.PlanError):
        score(frozen, [], chosen)


@pytest.mark.parametrize("change", ["rate", "nonfinite", "zero", "mixed_basis", "cap"])
def test_adverse_native_rates_counts_and_bases(frozen, change):
    receipt = native(frozen)
    sample = receipt["measurement"]["individual_runs"][0]
    if change == "rate":
        sample["throughput_tps"] = 999
    elif change == "nonfinite":
        sample["eval_duration_ms"] = math.inf
    elif change == "zero":
        sample.update(tokens_generated=0, throughput_tps=0)
    elif change == "mixed_basis":
        sample["ttft_basis"] = "client-stream-first-content"
    else:
        receipt["execution"]["request"]["options"]["num_predict"] = 3
    if change != "nonfinite":
        refresh(receipt)
    if change in ("rate", "nonfinite", "cap"):
        with pytest.raises(api.PlanError):
            score(frozen, [seal(receipt)])
    else:
        report = score(frozen, [seal(receipt)])
        assert report["exit_code"] == 3 and report["rows"][0]["relative_error"] is None


def test_installed_score_consumer_source_protocol_and_adverse_oracle(frozen, tmp_path, monkeypatch):
    """Source protocol only; hosted wheel/sdist jobs retain installed-origin enforcement."""
    from test_ci_acceptance import load_script
    from chimeraforge.cli import app

    script = load_script("ci_prediction_score")
    parent = load_script("ci_installed_acceptance")
    monkeypatch.setattr(parent, "assert_installed_origin", lambda *args: None)

    def source_cli(arguments, cwd, env, expected_code=0):
        result = CliRunner().invoke(app, arguments)
        assert result.exit_code == expected_code, result.output
        return result.output

    monkeypatch.setattr(parent, "run_cli", source_cli)
    source = tmp_path / "source.json"
    frozen.save(source)
    result = script.accept(tmp_path, {}, tmp_path / "checkout", source)
    assert result["installed_cli_outcomes"] == [0, 1, 2, 3]
    saved, index = script.synthetic_plan(source)
    native_receipt = script.protocol_receipt(saved, index)
    report = api.score_predictions(
        api.artifact_from_dict(saved),
        [native_receipt],
        policy={
            "plan_fingerprint": saved["fingerprint"],
            "candidate_indices": [index],
            "expected_receipts_per_index": {str(index): 1},
            "relative_error_band": 0.25,
        },
    ).to_dict()
    report["rows"][0]["relative_error"] = 0
    seal(report)
    with pytest.raises(AssertionError):
        script.validate(report, 0, saved, native_receipt)
    for phase in ("serving_before", "serving_after"):
        native_receipt["execution"][phase].update(device="cpu", hardware=None)
    receipt_path = tmp_path / "cpu-native.json"
    receipt_path.write_text(json.dumps(seal(native_receipt)))
    plan_path = tmp_path / "cpu-plan.json"
    plan_path.write_text(json.dumps(saved))
    actual = script.accept_cpu(tmp_path, {}, plan_path, index, receipt_path)
    assert actual["exit_code"] == 3 and actual["received"] == 1 and actual["comparable"] == 0


@pytest.mark.parametrize(
    "changes",
    [
        {"candidate_indices": [0, 0]},
        {"candidate_indices": [True]},
        {"expected_receipts_per_index": {"00": 1}},
        {"expected_receipts_per_index": {"0": 0}},
        {"expected_receipts_per_index": {"0": True}},
        {"relative_error_band": -1},
        {"relative_error_band": math.inf},
        {"relative_error_band": True},
        {"plan_fingerprint": "a" * 64},
        {"unknown": 1},
    ],
)
def test_policy_is_closed_explicit_and_strict(frozen, changes):
    with pytest.raises(api.PlanError):
        score(frozen, [], policy(frozen, **changes))


def test_cli_private_failures_atomic_and_alias_protection(frozen, tmp_path, monkeypatch):
    from chimeraforge.cli import app

    plan_path, receipt_path, policy_path = [
        tmp_path / name for name in ("plan.json", "bench.json", "policy.json")
    ]
    frozen.save(plan_path)
    receipt_path.write_text(json.dumps(native(frozen)))
    policy_path.write_text(json.dumps(policy(frozen)))
    args = [
        "score",
        "--plan",
        str(plan_path),
        "--policy",
        str(policy_path),
        "--benchmark",
        str(receipt_path),
        "--json",
    ]
    for source in (plan_path, receipt_path, policy_path):
        original = source.read_bytes()
        result = CliRunner().invoke(app, [*args, "--out", str(source)])
        assert result.exit_code == 2 and source.read_bytes() == original
    alias = tmp_path / "alias.json"
    os.link(receipt_path, alias)
    assert CliRunner().invoke(app, [*args, "--out", str(alias)]).exit_code == 2
    alias.unlink()
    out = tmp_path / "out.json"
    before = b"previous output"
    out.write_bytes(before)
    monkeypatch.setattr(
        "pathlib.Path.replace", lambda *a, **k: (_ for _ in ()).throw(OSError("private-token"))
    )
    result = CliRunner().invoke(app, [*args, "--out", str(out)])
    assert result.exit_code == 2 and out.read_bytes() == before
    assert "private-token" not in result.output and not list(tmp_path.glob("*.tmp"))
    policy_path.write_text('{"private-token":1,"private-token":2}')
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 2 and "private-token" not in result.output
