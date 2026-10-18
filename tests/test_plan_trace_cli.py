"""Plan-bound CLI admission errors must precede private input or endpoint contact."""

import json
import hashlib
from dataclasses import asdict
import os

import pytest
from typer.testing import CliRunner

from chimeraforge import api
from chimeraforge.cli import app


@pytest.fixture
def context(tmp_path, monkeypatch):
    from test_plan_trace import ObservedBackend, rows
    from chimeraforge.bench import trace

    saved = api.plan(
        api.PlanRequest(
            allow_network=False,
            budget=100000,
            avg_tokens=4,
            prompt_tokens=8,
            latency_slo=100000,
            ttft_slo=20000,
            tpot_slo=20000,
        )
    )
    plan, workload = tmp_path / "plan.json", tmp_path / "workload.json"
    saved.save(plan)
    workload.write_text(json.dumps([asdict(row) for row in rows()]), encoding="utf-8")
    backend = ObservedBackend(saved)
    monkeypatch.setattr(trace, "get_backend", lambda *args, **kwargs: backend)
    return saved, plan, workload, backend


@pytest.mark.asyncio
async def test_public_plan_trace_wrapper_executes_the_native_path(context):
    from test_plan_trace import rows

    saved, _, _, backend = context
    result = await api.replay_plan_trace(saved, rows())
    assert type(result) is api.PlanTraceReplay
    assert result.to_dict()["exit_code"] == 0 and backend.closed
    assert result.native_trace.to_dict() == result.to_dict()["native_trace"]


@pytest.mark.parametrize("bundle", [False, True])
@pytest.mark.parametrize("machine", [False, True])
def test_cli_plan_and_bundle_replay_keep_native_receipt_and_original_bytes(
    context, tmp_path, bundle, machine
):
    saved, plan, workload, backend = context
    source = tmp_path / "bundle" if bundle else plan
    if bundle:
        api.create_plan_bundle(plan, source)
    original_plan, original_workload = plan.read_bytes(), workload.read_bytes()
    output = tmp_path / "receipt.json"
    result = CliRunner().invoke(
        app,
        [
            "trace",
            str(workload),
            "--from-plan",
            str(source),
            "--out",
            str(output),
            *(["--json"] if machine else []),
        ],
    )
    assert result.exit_code == 0, result.output
    report = json.loads(output.read_bytes())
    if machine:
        assert json.loads(result.stdout) == report
    else:
        assert "Completed 2/2 requests" in result.stdout
    assert report["plan"]["fingerprint"] == saved.to_dict()["fingerprint"]
    assert report["plan"]["raw_sha256"] == hashlib.sha256(original_plan).hexdigest()
    assert report["workload"]["raw_sha256"] == hashlib.sha256(original_workload).hexdigest()
    assert report["native_trace"]["workload"]["raw_sha256"] is None
    assert report["status"] == "completed" and report["configuration_status"] == "unverified"
    assert "PRIVATE" not in json.dumps(report) and backend.closed
    assert plan.read_bytes() == original_plan and workload.read_bytes() == original_workload


def test_outside_hardlink_to_bundle_member_is_refused_before_endpoint_contact(context, tmp_path):
    _, plan, workload, backend = context
    directory = tmp_path / "bundle"
    api.create_plan_bundle(plan, directory)
    manifest = json.loads((directory / "manifest.json").read_bytes())
    member = directory / next(row["path"] for row in manifest["files"] if row["role"] == "corpus")
    original = member.read_bytes()
    alias = tmp_path / "outside-alias.json"
    os.link(member, alias)
    result = CliRunner().invoke(
        app,
        ["trace", str(workload), "--from-plan", str(directory), "--out", str(alias), "--json"],
    )
    assert result.exit_code == 2, result.output
    # The strict bundle reader refuses the newly shared member before output admission.
    assert json.loads(result.stdout)["error"] == "invalid saved plan or verified plan bundle"
    assert not backend.contacts and not backend.calls
    assert member.read_bytes() == alias.read_bytes() == original


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
