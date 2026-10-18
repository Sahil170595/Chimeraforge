"""Plan-bound CLI admission errors must precede private input or endpoint contact."""

import json

import pytest
from typer.testing import CliRunner

from chimeraforge import api
from chimeraforge.cli import app


def test_public_plan_trace_api_has_a_concrete_defensive_return_type():
    from typing import get_type_hints

    assert get_type_hints(api.replay_plan_trace)["return"] is api.PlanTraceReplay


@pytest.mark.parametrize(
    "options,message",
    [
        ([], "--model"),
        (["--candidate-index", "0", "--model", "served"], "--from-plan"),
        (["--from-plan", "missing-plan.json", "--backend", "ollama"], "--backend"),
        (["--from-plan", "missing-plan.json", "--latency-slo", "1"], "SLO"),
        (["--from-plan", "missing-plan.json", "--first-output-slo", "1"], "SLO"),
        (["--from-plan", "missing-plan.json", "--tpot-slo", "1"], "SLO"),
    ],
)
def test_explicit_plan_and_ordinary_modes_refuse_ignored_options(monkeypatch, options, message):
    def contact(*args, **kwargs):
        raise AssertionError("invalid CLI admission reached endpoint replay")

    monkeypatch.setattr(api, "replay_trace", contact)
    result = CliRunner().invoke(app, ["trace", "missing-workload.json", *options, "--json"])
    assert result.exit_code == 2, result.output
    assert message in json.loads(result.stdout)["error"]


@pytest.mark.parametrize("role", ["plan", "workload"])
def test_output_alias_is_refused_before_opening_or_replaying_inputs(tmp_path, role):
    plan, workload = tmp_path / "plan.json", tmp_path / "workload.json"
    plan.write_bytes(b"PRIVATE INVALID PLAN")
    workload.write_bytes(b"PRIVATE INVALID WORKLOAD")
    original = {plan: plan.read_bytes(), workload: workload.read_bytes()}
    result = CliRunner().invoke(
        app,
        [
            "trace",
            str(workload),
            "--from-plan",
            str(plan),
            "--out",
            str(plan if role == "plan" else workload),
            "--json",
        ],
    )
    assert result.exit_code == 2, result.output
    assert "cannot replace" in json.loads(result.stdout)["error"]
    assert all(path.read_bytes() == raw for path, raw in original.items())
