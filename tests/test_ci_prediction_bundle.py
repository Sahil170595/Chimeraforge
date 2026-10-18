"""Source consumer oracles; installed artifacts and native CPU evidence qualify separately."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import pytest
from typer.testing import CliRunner

from chimeraforge import api

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def script(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def saved_source(tmp_path):
    path = tmp_path / "original-plan.json"
    api.plan(
        api.PlanRequest(
            allow_network=False,
            quality_target=0,
            budget=100000,
            avg_tokens=4,
            prompt_tokens=8,
        )
    ).save(path)
    return path


def source_adapter(monkeypatch, consumer):
    from chimeraforge.cli import app

    installed = script("ci_installed_acceptance")
    monkeypatch.setattr(installed, "assert_installed_origin", lambda *_: None)
    calls = []

    def source_cli(arguments, cwd, env, expected_code=0):
        calls.append((arguments, expected_code))
        result = CliRunner().invoke(app, arguments)
        allowed = expected_code if isinstance(expected_code, tuple) else (expected_code,)
        assert result.exit_code in allowed, result.output
        return result.stdout

    monkeypatch.setattr(installed, "run_cli", source_cli)
    return installed, calls


def test_synthetic_fixtures_keep_original_private_bytes_and_independent_score_oracles(
    tmp_path, monkeypatch
):
    monkeypatch.syspath_prepend(str(SCRIPTS))
    consumer = script("ci_prediction_bundle")
    original = saved_source(tmp_path)
    raw = original.read_bytes()
    saved, policy, native = consumer.fixtures(original)
    assert original.read_bytes() == raw
    assert policy["plan_fingerprint"] == saved["fingerprint"]
    assert policy["expected_receipts_per_index"] == {str(native["plan"]["candidate_index"]): 1}
    assert consumer.PRIVATE_INPUT in json.dumps(native)
    result = api.score_predictions(api.artifact_from_dict(saved), [native], policy=policy).to_dict()
    assert result["exit_code"] == 0 and result["rows"][0]["measured"] == 32.0
    assert result["rows"][0]["predicted"] == 40.0
    assert consumer.PRIVATE_INPUT not in json.dumps(result)


def test_source_cli_bundle_consumer_checks_relocation_population_and_input_aliases(
    tmp_path, monkeypatch
):
    monkeypatch.syspath_prepend(str(SCRIPTS))
    consumer = script("ci_prediction_bundle")
    source = saved_source(tmp_path)
    original = source.read_bytes()
    _, calls = source_adapter(monkeypatch, consumer)
    result = consumer.accept(tmp_path, {}, tmp_path / "checkout", source)
    assert result["roundtrip"]["exit_code"] == 0
    assert result["known_breach"]["exit_code"] == 1
    assert result["zero_receipts"]["exit_code"] == 3
    assert result["duplicate_receipts"]["counts"]["duplicate"] == 2
    assert result["negative_receipt"]["counts"]["binding_mismatch"] == 1
    assert result["roundtrip"]["counts"]["received"] == 1
    assert result["roundtrip"]["counts"]["comparable"] == 1
    assert result["raw_receipt_preserved"] and result["source_inputs_unchanged"]
    assert result["malformed_inventory_refused"] and result["input_aliases_refused"]
    assert len(json.dumps(result).encode()) < 8192
    assert consumer.PRIVATE_INPUT not in json.dumps(result)
    assert {code for _, code in calls} == {0, 1, 2, 3}
    assert all(arguments[0] == "bundle" for arguments, _ in calls)
    assert source.read_bytes() == original


@pytest.mark.parametrize("mutation", ["policy_sha", "transport_bytes", "receipt_count", "private"])
def test_bundle_consumer_refuses_incorrect_public_metadata(tmp_path, monkeypatch, mutation):
    monkeypatch.syspath_prepend(str(SCRIPTS))
    consumer = script("ci_prediction_bundle")
    installed, _ = source_adapter(monkeypatch, consumer)
    source = saved_source(tmp_path)
    actual = installed.run_cli

    def corrupt(arguments, cwd, env, expected_code=0):
        raw = actual(arguments, cwd, env, expected_code)
        if arguments[1] != "prediction-create" or expected_code != 0:
            return raw
        report = json.loads(raw)
        if mutation == "policy_sha":
            report["policy_sha256"] = "0" * 64
        elif mutation == "transport_bytes":
            report["transport_bytes"] -= 1
        elif mutation == "receipt_count":
            report["receipt_count"] = 0
        else:
            report["limits"] += consumer.PRIVATE_INPUT
        return json.dumps(report)

    monkeypatch.setattr(installed, "run_cli", corrupt)
    with pytest.raises(AssertionError):
        consumer.accept(tmp_path, {}, tmp_path / "checkout", source)


def test_cpu_bundle_consumer_reuses_receipt_and_keeps_gpu_prediction_ineligible(
    tmp_path, monkeypatch
):
    monkeypatch.syspath_prepend(str(SCRIPTS))
    consumer = script("ci_prediction_bundle")
    source = saved_source(tmp_path)
    saved, policy, native = consumer.fixtures(source)
    plan = tmp_path / "cpu-plan.json"
    plan.write_text(json.dumps(saved))
    for phase in ("serving_before", "serving_after"):
        native["execution"][phase].update(device="cpu", hardware=None)
    from ci_prediction_score import seal

    receipt = tmp_path / "cpu-receipt.json"
    receipt.write_bytes((json.dumps(seal(native), indent=3) + "\n\n").encode())
    originals = (plan.read_bytes(), receipt.read_bytes())
    _, calls = source_adapter(monkeypatch, consumer)
    result = consumer.accept_cpu(tmp_path, {}, plan, policy["candidate_indices"][0], receipt)
    assert result["exit_code"] == 3
    assert result["counts"]["received"] == 1 and result["counts"]["comparable"] == 0
    assert result["counts"]["binding_mismatch"] == 1
    assert result["raw_receipt_preserved"] and result["extra_inference_requests"] == 0
    assert all(arguments[0] == "bundle" for arguments, _ in calls)
    assert originals == (plan.read_bytes(), receipt.read_bytes())


def test_existing_cpu_score_caller_passes_the_same_completed_receipt_to_bundle(
    tmp_path, monkeypatch
):
    monkeypatch.syspath_prepend(str(SCRIPTS))
    consumer = script("ci_prediction_bundle")
    scorer = script("ci_prediction_score")
    source = saved_source(tmp_path)
    saved, policy, native = consumer.fixtures(source)
    source.write_text(json.dumps(saved))
    for phase in ("serving_before", "serving_after"):
        native["execution"][phase].update(device="cpu", hardware=None)
    receipt = tmp_path / "existing-cpu-receipt.json"
    receipt.write_text(json.dumps(scorer.seal(native)))
    original = receipt.read_bytes()
    _, calls = source_adapter(monkeypatch, consumer)
    handed = []

    def offline_bundle(cwd, env, plan, index, benchmark):
        handed.append((plan, index, benchmark))
        return {"existing_receipt_reused": True}

    monkeypatch.setattr(consumer, "accept_cpu", offline_bundle)
    index = policy["candidate_indices"][0]
    result = scorer.accept_cpu(tmp_path, {}, source, index, receipt)
    assert handed == [(source, index, receipt)]
    assert result["prediction_bundle"] == {"existing_receipt_reused": True}
    assert result["exit_code"] == 3 and [arguments[0] for arguments, _ in calls] == ["score"]
    assert receipt.read_bytes() == original
