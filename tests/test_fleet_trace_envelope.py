"""Finite envelope controls use current native whole-fleet CPU protocol execution."""

import asyncio
import copy
from dataclasses import replace
import hashlib
import json
import os
import subprocess
import sys

import pytest

from chimeraforge import api
from chimeraforge.bench import trace
from test_fleet_monitor import make_native_fleet
from test_fleet_trace import Node, Scene, endpoints, routes, workload


@pytest.fixture(scope="module")
def population(tmp_path_factory):
    root = tmp_path_factory.mktemp("fleet-envelope")
    saved, indices = make_native_fleet(tpot_slo=1000)
    index = indices["vllm"]
    plan = root / "original.json"
    saved.save(plan)
    scene = Scene(saved, index)
    campaigns = {}

    async def execute():
        for name, interval in (("lower", 0.002), ("higher", 0.001)):
            requests = [
                replace(row, arrival_offset_s=i * interval)
                for i, row in enumerate(workload(saved, index))
            ]
            campaigns[name] = (
                await api.replay_fleet_trace_campaign(
                    plan,
                    requests,
                    endpoints(),
                    routes(requests),
                    candidate_index=index,
                    executions=2,
                    concurrency=3,
                    request_timeout=2,
                    trace_timeout=5,
                    cleanup_timeout=2,
                    campaign_timeout=20,
                )
            ).to_dict()

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(trace, "get_backend", scene.factory)
        asyncio.run(execute())
    assert all(node.closed for node in scene.created)
    assert sum(len(node.calls) for node in scene.created) == 24
    manifest = campaigns["lower"]["manifest"]
    controls = manifest["controls"]
    cases = {
        "schema_version": 1,
        "kind": "chimeraforge.fleet-trace-envelope-cases",
        **{
            name: controls[name]
            for name in (
                "model",
                "backend",
                "concurrency",
                "request_timeout_seconds",
                "trace_timeout_seconds",
                "campaign_timeout_seconds",
                "cleanup_timeout_seconds",
            )
        },
        "expected_executions": 2,
        "original_replicas": 3,
        "model_override": None,
        "endpoints": manifest["endpoints"],
        "routes": manifest["routes"]["rows"],
        "ordered_descriptors": [
            {k: v for k, v in row.items() if k != "arrival_offset_s"}
            for row in manifest["ordered_descriptors"]
        ],
        "cells": [
            {"name": "lower", "arrival_interval_seconds": 0.002},
            {"name": "higher", "arrival_interval_seconds": 0.001},
        ],
    }
    policy = {
        "schema_version": 1,
        "kind": "chimeraforge.fleet-trace-envelope-policy",
        "targets": controls["targets"],
        "fixed_controls": {"version": "controlled-source"},
        "require_cache_evidence": False,
    }
    return plan, index, cases, policy, campaigns


def test_native_whole_fleet_points_preserve_k_n_and_every_request(population):
    plan, index, cases, policy, campaigns = population
    report = api.assess_fleet_trace_envelope(
        plan,
        cases,
        campaigns,
        policy=policy,
        candidate_index=index,
    ).to_dict()
    assert report["exit_code"] == 0 and report["outcome"] == "conditional_pass"
    assert report["highest_observed_passing"]["cell_index"] == 1
    assert report["highest_observed_passing"]["nominal_rate_rps"] == 1000
    assert len(report["cells"]) == 2
    for cell in report["cells"]:
        assert cell["original_replicas"] == 3 and cell["expected_executions"] == 2
        assert cell["requests_per_execution"] == 6 and cell["total_requests"] == 12
        assert cell["outcome"] == "observed_pass" and cell["eligible_for_point"]
        assert len(cell["executions"]) == 2
        assert all(
            len(slot["members"]) == 3 and len(slot["rows"]) == 6 for slot in cell["executions"]
        )
    public = json.dumps(report)
    assert "PRIVATE PROMPT" not in public and "member-0" not in public
    assert ".invalid" not in public and str(plan) not in public


def assess(population, *, cases=None, policy=None, campaigns=None):
    plan, index, original_cases, original_policy, original_campaigns = population
    return api.assess_fleet_trace_envelope(
        plan,
        original_cases if cases is None else cases,
        original_campaigns if campaigns is None else campaigns,
        policy=original_policy if policy is None else policy,
        candidate_index=index,
    ).to_dict()


def produce(
    population, scenario, *, chat=False, interval=0.001, facts_sequence=None, cache_sequence=None
):
    plan, index, cases, _, _ = population
    saved = api.load_plan(plan)
    scene = Scene(saved, index)

    class ControlledNode(Node):
        async def generate_observed(self, *args):
            if scenario == "partial" and self.url == endpoints()[0].url:
                raise RuntimeError("private controlled incomplete generation")
            result = await super().generate_observed(*args)
            if self.cached_override is not None:
                result.native["cached_prompt_tokens"] = self.cached_override
            if scenario == "breach":
                result.native["eval_duration_ms"] = 2000 * (result.native["tokens_generated"] - 1)
                result.native["throughput_tps"] = 0.5
                return replace(result, mean_tpot_ms=2000)
            return result

        async def chat_observed(self, model, messages, options, on_first_output):
            return await self.generate_observed(model, "controlled-chat", options, on_first_output)

    def factory(name, *, base_url, **kwargs):
        node = ControlledNode(scene, name, base_url)
        execution_index = len(scene.created) // 3
        node.cached_override = None if cache_sequence is None else cache_sequence[execution_index]
        for key, values in (facts_sequence or {}).items():
            value = values[execution_index]
            if value is None:
                node.observed.pop(key, None)
            else:
                node.observed[key] = value
        if scenario == "unknown":
            node.observed.pop("model")
        if scenario == "changed-version":
            node.observed["version"] = "changed-control"
        scene.created.append(node)
        return node

    requested = [
        replace(row, arrival_offset_s=i * interval) for i, row in enumerate(workload(saved, index))
    ]
    if chat:
        requested = [
            api.ChatTraceRequest(
                row.request_id,
                (
                    api.ChatMessage("system", "private-system"),
                    api.ChatMessage("user", "private-chat-" + str(i)),
                ),
                row.max_output_tokens,
                row.arrival_offset_s,
                temperature=0.25,
            )
            for i, row in enumerate(requested)
        ]
    routed = routes(requested, empty_last=scenario == "inactive")
    if scenario == "routes":
        routed = list(
            reversed(
                [
                    api.TraceRoute(row.request_id, "member-" + str((i + 1) % 3))
                    for i, row in enumerate(requested)
                ]
            )
        )
    declared_endpoints = endpoints()
    if scenario == "members":
        declared_endpoints = tuple(
            api.FleetEndpoint("changed-" + row.id, row.url) for row in declared_endpoints
        )
        routed = [api.TraceRoute(row.request_id, "changed-" + row.endpoint_id) for row in routed]
    stop = asyncio.Event()
    if scenario == "stopped":
        stop.set()

    async def execute():
        return (
            await api.replay_fleet_trace_campaign(
                plan,
                requested,
                declared_endpoints,
                routed,
                candidate_index=index,
                executions=1 if scenario == "K" else 2,
                concurrency=cases["concurrency"],
                request_timeout=2,
                trace_timeout=5,
                cleanup_timeout=2,
                campaign_timeout=20,
                stop_event=stop,
            )
        ).to_dict()

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(trace, "get_backend", factory)
        result = asyncio.run(execute())
    assert all(node.closed for node in scene.created)
    return result


def test_known_versions_after_unknown_first_block_all_points(population):
    policy = {**population[3], "fixed_controls": {}}
    campaigns = {
        "lower": produce(
            population, "complete", interval=0.002, facts_sequence={"version": [None, "A"]}
        ),
        "higher": produce(population, "complete", facts_sequence={"version": ["B", "B"]}),
    }
    assert all(
        api.load_fleet_trace_campaign(value).to_dict() == value for value in campaigns.values()
    )
    report = assess(population, policy=policy, campaigns=campaigns)
    assert report["exit_code"] == 3 and report["highest_observed_passing"] is None
    assert "member_condition_changed:condition:version" in report["blockers"]


def test_known_cache_contradiction_after_unknown_first_blocks_all_points(population):
    policy = {**population[3], "fixed_controls": {}}
    campaigns = {
        "lower": produce(
            population,
            "complete",
            interval=0.002,
            facts_sequence={"prefix_cache": [None, False]},
            cache_sequence=[None, None],
        ),
        "higher": produce(
            population,
            "complete",
            facts_sequence={"prefix_cache": [None, None]},
            cache_sequence=[1, 1],
        ),
    }
    assert all(
        api.load_fleet_trace_campaign(value).to_dict() == value for value in campaigns.values()
    )
    report = assess(population, policy=policy, campaigns=campaigns)
    assert report["exit_code"] == 3 and report["highest_observed_passing"] is None
    assert "observed_cache_hits_changed" in report["blockers"]


def test_partial_native_child_keeps_descriptive_complete_passing_point(population):
    campaigns = {**population[4], "higher": produce(population, "partial")}
    assert api.load_fleet_trace_campaign(campaigns["higher"]).to_dict() == campaigns["higher"]
    child = campaigns["higher"]["executions"][0]["receipt"]
    assert child is not None and 0 < child["native_trace"]["execution"]["completed"] < 6
    report = assess(population, campaigns=campaigns)
    assert report["exit_code"] == 3
    assert report["highest_observed_passing"]["cell_index"] == 0
    assert "mean_timing_basis_changed" not in report["blockers"]


def test_missing_grid_retains_whole_declared_population(population):
    report = assess(population, campaigns={})
    assert report["exit_code"] == 3 and report["highest_observed_passing"] is None
    assert len(report["cells"]) == 2
    assert (
        sum(len(execution["rows"]) for cell in report["cells"] for execution in cell["executions"])
        == 24
    )
    assert all(cell["outcome"] == "unknown" for cell in report["cells"])
    partial = assess(population, campaigns={"lower": population[4]["lower"]})
    assert partial["exit_code"] == 3
    assert partial["highest_observed_passing"]["cell_index"] == 0


@pytest.mark.parametrize("scenario", ["stopped", "inactive", "unknown", "changed-version"])
def test_whole_member_eligibility_blocks_unknown_or_incomplete(population, scenario):
    campaigns = {**population[4], "higher": produce(population, scenario)}
    if scenario == "inactive":
        altered_cases = copy.deepcopy(population[2])
        altered_cases["routes"] = campaigns["higher"]["manifest"]["routes"]["rows"]
        campaigns = {"higher": campaigns["higher"]}
    else:
        altered_cases = None
    report = assess(population, cases=altered_cases, campaigns=campaigns)
    assert report["exit_code"] == 3 and not report["cells"][1]["eligible_for_point"]
    assert all(len(slot["members"]) == 3 for slot in report["cells"][1]["executions"])
    if scenario == "inactive":
        assert all(
            slot["members"][2]["row_indices"] == [] for slot in report["cells"][1]["executions"]
        )
        assert "inactive_member" in report["cells"][1]["blockers"]


def test_native_breach_and_incomplete_priority_preserve_known_breaches(population):
    breached = produce(population, "breach")
    report = assess(population, campaigns={**population[4], "higher": breached})
    assert report["exit_code"] == 1 and report["outcome"] == "observed_breach"
    assert len(report["known_breaches"]) == 12
    assert report["highest_observed_passing"]["cell_index"] == 0
    report = assess(population, campaigns={"higher": breached})
    assert report["exit_code"] == 3 and len(report["known_breaches"]) == 12


@pytest.mark.parametrize("scenario", ["routes", "members", "K"])
def test_genuine_alternate_native_population_is_refused(population, scenario):
    with pytest.raises(api.PlanError):
        assess(population, campaigns={**population[4], "higher": produce(population, scenario)})


@pytest.mark.parametrize(
    "field",
    [
        "original_replicas",
        "expected_executions",
        "model",
        "backend",
        "model_override",
        "concurrency",
        "cleanup_timeout_seconds",
        "request_timeout_seconds",
        "trace_timeout_seconds",
        "campaign_timeout_seconds",
    ],
)
def test_closed_declaration_mismatch_and_boolean_counts_refuse(population, field):
    cases = copy.deepcopy(population[2])
    cases[field] = (
        True if field in ("original_replicas", "expected_executions") else "private-invalid"
    )
    with pytest.raises(api.PlanError, match="invalid fleet trace envelope"):
        assess(population, cases=cases)


def test_plan_targets_cannot_be_overridden_and_late_cases_admit_before_receipts(
    population, monkeypatch
):
    from chimeraforge.bench import fleet_envelope_inputs

    calls = []

    def forbidden(*args, **kwargs):
        calls.append(1)
        raise AssertionError("receipt parsed before declaration admission")

    monkeypatch.setattr(fleet_envelope_inputs, "held_campaign", forbidden)
    cases = copy.deepcopy(population[2])
    cases["cells"][-1]["arrival_interval_seconds"] = float("nan")
    with pytest.raises(api.PlanError):
        assess(population, cases=cases)
    policy = copy.deepcopy(population[3])
    policy["targets"]["tpot_ms"] *= 2
    with pytest.raises(api.PlanError):
        assess(population, policy=policy)
    assert calls == []


def test_chat_commitments_preserve_mode_order_and_temperature(population):
    campaign = produce(population, "complete", chat=True)
    cases = copy.deepcopy(population[2])
    cases["cells"] = [cases["cells"][1]]
    cases["ordered_descriptors"] = [
        {k: v for k, v in row.items() if k != "arrival_offset_s"}
        for row in campaign["manifest"]["ordered_descriptors"]
    ]
    report = assess(population, cases=cases, campaigns={"higher": campaign})
    assert report["exit_code"] == 0
    for mutation in ("temperature", "order", "mode"):
        altered = copy.deepcopy(cases)
        row = altered["ordered_descriptors"][0]
        if mutation == "temperature":
            row["temperature"] = 0.5
        elif mutation == "order":
            row["messages"].reverse()
        else:
            row["mode"] = "completion"
        with pytest.raises(api.PlanError):
            assess(population, cases=altered, campaigns={"higher": campaign})


def test_offline_receiving_and_complete_output_bound(population, monkeypatch, tmp_path):
    from chimeraforge.bench import fleet_envelope

    def forbidden(*args, **kwargs):
        raise AssertionError("offline assessment contacted a backend")

    monkeypatch.setattr(trace, "get_backend", forbidden)
    report = assess(population)
    assert report["exit_code"] == 0
    monkeypatch.setattr(fleet_envelope, "MAX_OUTPUT_BYTES", 128)
    with pytest.raises(api.PlanError):
        assess(population)
    assert list(tmp_path.iterdir()) == []


def test_input_protection_and_raw_hash_basis(population, tmp_path):
    plan, index, cases, policy, campaigns = population
    result = api.assess_fleet_trace_envelope(
        plan, cases, campaigns, policy=policy, candidate_index=index
    )
    before = plan.read_bytes()
    with pytest.raises(api.PlanError):
        result.save(plan)
    assert plan.read_bytes() == before
    assert result.to_dict()["source"]["raw_sha256"] == hashlib.sha256(before).hexdigest()
    alien = tmp_path / "different-plan.json"
    alien.write_bytes(before + b"\n")
    with pytest.raises(api.PlanError):
        api.assess_fleet_trace_envelope(
            alien, cases, campaigns, policy=policy, candidate_index=index
        )


def seal(value):
    from chimeraforge.planner.replay import digest

    value["fingerprint"] = digest(
        {key: item for key, item in value.items() if key != "fingerprint"}
    )


def test_copied_execution_under_new_clock_and_date_blocks_all_points(population):
    campaigns = copy.deepcopy(population[4])
    campaign = campaigns["higher"]
    first, second = campaign["executions"]
    child = copy.deepcopy(first["receipt"])
    child["created_at"] = "2026-11-01T00:00:00Z"
    child["native_trace"]["created_at"] = child["created_at"]
    offset = second["start_s"] + 0.001
    child["native_trace"]["clock"]["origin"] = campaign["clock"]["origin"] + offset
    second["end_s"] = offset + child["native_trace"]["execution"]["elapsed_seconds"] + 0.001
    campaign["clock"]["elapsed_seconds"] = max(
        campaign["clock"]["elapsed_seconds"], second["end_s"]
    )
    seal(child["native_trace"])
    seal(child)
    second["receipt"] = child
    seal(campaign)
    assert api.load_fleet_trace_campaign(campaign).to_dict() == campaign
    report = assess(population, campaigns=campaigns)
    assert report["exit_code"] == 3 and report["highest_observed_passing"] is None
    assert "duplicate_execution_payload" in report["blockers"]
    assert all(not cell["eligible_for_point"] for cell in report["cells"])


def test_native_aggregate_input_byte_boundary(population, monkeypatch):
    from chimeraforge.bench import fleet_envelope_inputs
    from chimeraforge.bench.fleet_campaign_receipt import held_campaign

    size = sum(held_campaign(value)["size_bytes"] for value in population[4].values())
    monkeypatch.setattr(fleet_envelope_inputs, "MAX_CAMPAIGN_TOTAL_BYTES", size)
    assert assess(population)["budgets"]["campaign_bytes"] == size
    monkeypatch.setattr(fleet_envelope_inputs, "MAX_CAMPAIGN_TOTAL_BYTES", size - 1)
    with pytest.raises(api.PlanError):
        assess(population)


def test_cli_missing_malformed_and_alias_destinations(population, tmp_path):
    from typer.testing import CliRunner
    from chimeraforge.cli import app

    plan, index, cases, policy, campaigns = population
    paths = {}
    for name, data in {"cases": cases, "policy": policy, **campaigns}.items():
        paths[name] = tmp_path / (name + ".json")
        paths[name].write_text(json.dumps(data), encoding="utf-8")
    args = [
        "trace-envelope",
        "--fleet",
        "--plan",
        str(plan),
        "--candidate-index",
        str(index),
        "--cases",
        str(paths["cases"]),
        "--policy",
        str(paths["policy"]),
        "--json",
    ]
    full = [
        *args,
        "--campaign",
        "lower=" + str(paths["lower"]),
        "--campaign",
        "higher=" + str(paths["higher"]),
    ]
    missing = subprocess.run(
        [sys.executable, "-B", "-m", "chimeraforge", *args],
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert (
        missing.returncode == 3 and json.loads(missing.stdout)["highest_observed_passing"] is None
    )
    for target in (plan, *paths.values()):
        before = target.read_bytes()
        result = CliRunner().invoke(app, [*full, "--out", str(target)])
        assert result.exit_code == 2 and "error" in json.loads(result.output)
        assert target.read_bytes() == before
    output = tmp_path / "assessment.json"
    output.write_bytes(b"sentinel")
    malformed = copy.deepcopy(campaigns["higher"])
    malformed["executions"][-1]["index"] = True
    seal(malformed)
    paths["higher"].write_text(json.dumps(malformed), encoding="utf-8")
    failed = subprocess.run(
        [sys.executable, "-B", "-m", "chimeraforge", *full, "--out", str(output)],
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert failed.returncode == 2 and set(json.loads(failed.stdout)) == {"error"}
    assert output.read_bytes() == b"sentinel"


def test_cli_output_overflow_refuses_before_any_assessment_publication(
    population, monkeypatch, tmp_path
):
    from typer.testing import CliRunner
    from chimeraforge.cli import app
    from chimeraforge.bench import fleet_envelope

    plan, index, cases, policy, campaigns = population
    paths = {}
    for name, data in {"cases": cases, "policy": policy, **campaigns}.items():
        paths[name] = tmp_path / (name + ".json")
        paths[name].write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(fleet_envelope, "MAX_OUTPUT_BYTES", 128)
    args = [
        "trace-envelope",
        "--fleet",
        "--plan",
        str(plan),
        "--candidate-index",
        str(index),
        "--cases",
        str(paths["cases"]),
        "--policy",
        str(paths["policy"]),
        "--campaign",
        "lower=" + str(paths["lower"]),
        "--campaign",
        "higher=" + str(paths["higher"]),
        "--json",
    ]
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 2 and set(json.loads(result.output)) == {"error"}


def test_actual_cli_fleet_envelope(population, tmp_path):
    plan, index, cases, policy, campaigns = population
    paths = {}
    for name, value in {"cases": cases, "policy": policy, **campaigns}.items():
        paths[name] = tmp_path / (name + ".json")
        paths[name].write_text(json.dumps(value), encoding="utf-8")
    command = [
        sys.executable,
        "-B",
        "-m",
        "chimeraforge",
        "trace-envelope",
        "--fleet",
        "--plan",
        str(plan),
        "--candidate-index",
        str(index),
        "--cases",
        str(paths["cases"]),
        "--policy",
        str(paths["policy"]),
        "--campaign",
        "lower=" + str(paths["lower"]),
        "--campaign",
        "higher=" + str(paths["higher"]),
        "--json",
    ]
    result = subprocess.run(
        command, env=os.environ.copy(), capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["kind"] == "chimeraforge.fleet-trace-envelope-assessment"
    assert report["highest_observed_passing"]["nominal_rate_rps"] == 1000
