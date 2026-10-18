"""Source consumer oracles; installed-distribution qualification runs separately in CI."""

import importlib.util
import json
from pathlib import Path
import sys

import pytest
from typer.testing import CliRunner

from chimeraforge import api
from chimeraforge.bench.trace_campaign_inputs import load_campaign
from chimeraforge.planner.replay import digest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def script(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_synthetic_uniform_fixture_retains_native_population_and_private_commitments(monkeypatch):
    monkeypatch.syspath_prepend(str(SCRIPTS))
    consumer = script("ci_trace_envelope")
    cases, policy, campaigns = consumer.fixtures()
    assert cases["expected_replicates"] == 2 and len(cases["ordered_descriptors"]) == 2
    assert policy["targets"] == {"latency_ms": 2000.0, "first_output_ms": None, "tpot_ms": None}
    assert policy["fixed_controls"] == {"device": "cpu"}
    for cell in cases["cells"]:
        campaign = load_campaign(campaigns[cell["name"]])
        assert len(campaign["replicas"]) == 2
        manifest = campaign["data"]["manifest"]
        assert [row["arrival_offset_s"] for row in manifest["ordered_descriptors"]] == [
            0.0,
            cell["arrival_interval_seconds"],
        ]
        for replica in campaign["replicas"]:
            assert replica["data"]["workload"]["raw_sha256"] is None
            assert replica["execution"]["planned"] == replica["execution"]["completed"] == 2
    assert consumer.PRIVATE_INPUT not in json.dumps([cases, policy, campaigns])


def test_synthetic_breach_changes_slo_not_execution_completion(monkeypatch):
    monkeypatch.syspath_prepend(str(SCRIPTS))
    consumer = script("ci_trace_envelope")
    value = load_campaign(consumer.uniform_campaign(0.5, durations=(0.12, 3.0)))
    assert value["data"]["exit_code"] == 0
    rows = value["replicas"][1]["data"]["requests"]
    assert all(row["slo"]["joint"] == "breach" for row in rows)
    assert all(row["timing"]["latency_ms"] == 3000.0 for row in rows)


def test_actual_cli_consumer_retains_each_outcome_and_protects_original_bytes(
    tmp_path, monkeypatch
):
    from chimeraforge.cli import app

    monkeypatch.syspath_prepend(str(SCRIPTS))
    installed = script("ci_installed_acceptance")
    consumer = script("ci_trace_envelope")
    monkeypatch.setattr(installed, "assert_installed_origin", lambda *_: None)
    calls = []

    def source_cli(arguments, cwd, env, expected_code=0):
        calls.append((arguments, expected_code))
        result = CliRunner().invoke(app, arguments)
        assert result.exit_code == expected_code, result.output
        return result.stdout

    monkeypatch.setattr(installed, "run_cli", source_cli)
    result = consumer.accept(tmp_path, {}, tmp_path / "checkout")
    assert result["full_population"]["assessment"]["exit_code"] == 0
    assert result["missing_higher"]["assessment"]["exit_code"] == 3
    assert result["known_breach"]["assessment"]["exit_code"] == 1
    assert result["full_population"]["counts"]["declared_cells"] == 2
    assert result["missing_higher"]["counts"]["missing_replicas"] == 2
    assert result["known_breach"]["counts"]["known_breaches"] == 2
    assert result["source_inputs_checked"] == 4
    assert all(arguments[0] == "trace-envelope" for arguments, _ in calls)
    assert {code for _, code in calls} == {0, 1, 2, 3}
    assert "independent" in result["scope"] and "synthetic" in result["scope"]


@pytest.mark.parametrize("mutation", ["missing_replica", "unknown_kind", "private_output"])
def test_actual_cli_oracle_refuses_resealed_invalid_response(tmp_path, monkeypatch, mutation):
    from chimeraforge.cli import app

    monkeypatch.syspath_prepend(str(SCRIPTS))
    installed = script("ci_installed_acceptance")
    consumer = script("ci_trace_envelope")
    monkeypatch.setattr(installed, "assert_installed_origin", lambda *_: None)
    mutations = []

    def source_cli(arguments, cwd, env, expected_code=0):
        result = CliRunner().invoke(app, arguments)
        assert result.exit_code == expected_code, result.output
        report = json.loads(result.stdout)
        if expected_code == 0:
            mutations.append(mutation)
            if mutation == "missing_replica":
                report["cells"][0]["replicas"].pop()
            elif mutation == "unknown_kind":
                report["kind"] = "unknown"
            else:
                report["limits"] += consumer.PRIVATE_INPUT
            report["fingerprint"] = digest(
                {key: value for key, value in report.items() if key != "fingerprint"}
            )
            Path(arguments[arguments.index("--out") + 1]).write_text(json.dumps(report))
        return json.dumps(report)

    monkeypatch.setattr(installed, "run_cli", source_cli)
    with pytest.raises((AssertionError, api.PlanError)):
        consumer.accept(tmp_path, {}, tmp_path / "checkout")
    assert mutations == [mutation]
