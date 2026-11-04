"""Source signed-gate consumer probes; installed and actual CPU proof run separately."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from typer.testing import CliRunner

from chimeraforge import api

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
SOURCE = Path(api.__file__).resolve().parents[1]


def script(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def source_adapter(monkeypatch):
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
    actual = subprocess.run

    def source_process(command, **kwargs):
        assert command[:3] == [sys.executable, "-I", "-B"]
        command = list(command)
        index = command.index("-c") + 1
        command[index] = f"import sys;sys.path.insert(0,{str(SOURCE)!r});" + command[index]
        kwargs["env"] = {**os.environ, **kwargs["env"]}
        return actual(command, **kwargs)

    monkeypatch.setattr(subprocess, "run", source_process)
    return installed, calls


def test_signed_gate_fixtures_are_private_and_independent_metric_expectations(monkeypatch):
    monkeypatch.syspath_prepend(str(SCRIPTS))
    consumer = script("ci_signed_contribution")
    left, right, policy = consumer.gate_fixtures()
    expected = consumer.native_expectation(left, right, "synthetic-protocol", 3)
    assert expected["exit_code"] == 0
    assert expected["values"]["baseline"] == {"completed_token_rate_tps": 12.0, "ttft_ms": 2.0}
    assert expected["values"]["candidate"]["completed_token_rate_tps"] == 12.0 / 0.9
    assert policy["rules"] == {"completed_token_rate_tps": 0.05, "ttft_ms": 0.1}
    signed = api.sign_contribution(left, consumer.SEED)
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    key = Ed25519PrivateKey.from_private_bytes(consumer.SEED).public_key().public_bytes_raw()
    verified = api.verify_signed_contribution(signed, trusted_keys=(key,)).to_dict()
    assert verified["exit_code"] == 0
    assert consumer.PRIVATE_GATE_INPUT not in json.dumps(verified)
    assert consumer.PRIVATE_GATE_INPUT in json.dumps(left)


@pytest.mark.parametrize("mutation", ["regression", "device", "cache", "options", "unknown_timing"])
def test_cpu_oracle_derives_outcomes_without_using_gate_scorer(monkeypatch, mutation):
    monkeypatch.syspath_prepend(str(SCRIPTS))
    consumer = script("ci_signed_contribution")
    left, right, _ = consumer.gate_fixtures()
    expected = 3
    if mutation == "regression":
        right["execution"]["elapsed_seconds"] = 2.0
        expected = 1
    elif mutation == "device":
        right["execution"]["serving_after"]["device"] = "gpu"
    elif mutation == "cache":
        right["measurement"]["individual_runs"][0]["cached_prompt_tokens"] = 1
    elif mutation == "options":
        right["execution"]["request"]["options"]["num_ctx"] += 1
    else:
        right["measurement"]["individual_runs"][0]["ttft_basis"] = "unknown"
    assert (
        consumer.native_expectation(left, right, "synthetic-protocol", 3)["exit_code"] == expected
    )


def test_actual_source_cli_signed_gate_consumer_preserves_negative_cases_and_compact_output(
    tmp_path, monkeypatch
):
    monkeypatch.syspath_prepend(str(SCRIPTS))
    consumer = script("ci_signed_contribution")
    _, calls = source_adapter(monkeypatch)
    report = consumer.accept_gate(tmp_path, {}, tmp_path / "checkout")
    assert {
        name: report[name]["exit_code"]
        for name in ("pass", "regression", "untrusted", "invalid", "partial", "semantic_copy")
    } == {
        "pass": 0,
        "regression": 1,
        "untrusted": 3,
        "invalid": 1,
        "partial": 3,
        "semantic_copy": 3,
    }
    assert report["pass"]["counts"] == {"baseline": 1, "candidate": 1, "pairs": 1}
    assert report["without_crypto"] == {"v1": "PASS", "gate_exit": 3}
    assert report["input_aliases_refused"] and report["source_bytes_unchanged"]
    assert len(json.dumps(report).encode()) < 8192
    assert consumer.PRIVATE_GATE_INPUT not in json.dumps(report)
    assert {code for _, code in calls} == {0, 1, 2, 3}
    assert all(args[:2] in (["contribute", "sign"], ["contribute", "gate"]) for args, _ in calls)


@pytest.mark.parametrize("mutation", ["metric", "trust", "population", "policy", "private"])
def test_consumer_refuses_resealed_incorrect_gate_report(tmp_path, monkeypatch, mutation):
    monkeypatch.syspath_prepend(str(SCRIPTS))
    consumer = script("ci_signed_contribution")
    installed, _ = source_adapter(monkeypatch)
    actual = installed.run_cli

    def corrupt(arguments, cwd, env, expected_code=0):
        raw = actual(arguments, cwd, env, expected_code)
        if arguments[:2] != ["contribute", "gate"] or expected_code != 0:
            return raw
        report = json.loads(raw)
        if mutation == "metric":
            report["comparisons"][0]["metrics"]["completed_token_rate_tps"]["candidate"] = 999
        elif mutation == "trust":
            report["candidate"][0]["trust_state"] = "untrusted_key"
        elif mutation == "population":
            report["candidate"].clear()
        elif mutation == "policy":
            report["policy"]["rules"]["completed_token_rate_tps"] = 0.9
        else:
            report["limits"] += consumer.PRIVATE_GATE_INPUT
        from chimeraforge.signed_payload import hash_json

        report["fingerprint"] = hash_json({k: v for k, v in report.items() if k != "fingerprint"})
        output = Path(arguments[arguments.index("--out") + 1])
        output.write_text(json.dumps(report))
        return json.dumps(report)

    monkeypatch.setattr(installed, "run_cli", corrupt)
    with pytest.raises(AssertionError):
        consumer.accept_gate(tmp_path, {}, tmp_path / "checkout")


def test_cpu_signed_gate_consumes_only_existing_two_native_receipts(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(SCRIPTS))
    consumer = script("ci_signed_contribution")
    left, right, _ = consumer.gate_fixtures()
    paths = [tmp_path / name for name in ("actual-baseline.json", "actual-candidate.json")]
    for path, native in zip(paths, (left, right)):
        path.write_text(json.dumps(native))
    originals = [path.read_bytes() for path in paths]
    _, calls = source_adapter(monkeypatch)
    result = consumer.accept_cpu_gate(tmp_path, {}, *paths, "synthetic-protocol", 3)
    assert result["exit_code"] == 0 and result["extra_inference_requests"] == 0
    assert result["counts"] == {"baseline": 1, "candidate": 1, "pairs": 1}
    assert originals == [path.read_bytes() for path in paths]
    assert all(args[:2] in (["contribute", "sign"], ["contribute", "gate"]) for args, _ in calls)


def test_existing_cpu_caller_hands_its_two_receipts_to_offline_signed_gate(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(SCRIPTS))
    consumer = script("ci_signed_contribution")
    native_gate = script("ci_regression_gate")
    left, right, _ = consumer.gate_fixtures()
    for native in (left, right):
        native["plan"] = {"served_model": "synthetic-protocol"}
        consumer._seal(native)
    baseline = tmp_path / "existing-baseline.json"
    baseline.write_text(json.dumps(left))
    original = baseline.read_bytes()
    installed, calls = source_adapter(monkeypatch)
    source_cli = installed.run_cli
    benchmark_calls, handed = [], []

    def existing_bench(arguments, cwd, env, expected_code=0):
        if arguments[0] != "bench":
            return source_cli(arguments, cwd, env, expected_code)
        benchmark_calls.append(arguments)
        output = Path(arguments[arguments.index("--output-dir") + 1])
        output.mkdir()
        (output / "plan-bench_fixture.json").write_text(json.dumps(right))
        return json.dumps(right)

    def offline_gate(cwd, env, left_path, right_path, version, runs):
        handed.append((left_path, right_path, version, runs))
        return {"existing_receipts_reused": True}

    monkeypatch.setattr(installed, "run_cli", existing_bench)
    monkeypatch.setattr(consumer, "accept_cpu_gate", offline_gate)
    report = native_gate.accept_cpu(
        tmp_path,
        {},
        tmp_path / "already-saved-plan.json",
        0,
        baseline,
        "synthetic-protocol",
        "http://unused",
        "synthetic-protocol",
        3,
    )
    candidate = tmp_path / "gate-real-candidate/plan-bench_fixture.json"
    assert handed == [(baseline, candidate, "synthetic-protocol", 3)]
    assert report["signed_native_gate"] == {"existing_receipts_reused": True}
    assert len(benchmark_calls) == 1 and [args[0] for args, _ in calls] == ["gate", "gate"]
    assert baseline.read_bytes() == original
