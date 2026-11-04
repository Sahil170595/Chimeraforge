"""Synthetic whole-fleet decisions, never independent serving measurements."""

from __future__ import annotations

import asyncio
import copy
from dataclasses import replace
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from chimeraforge import api
from chimeraforge.bench import trace
from chimeraforge.bench.fleet_trace_inputs import prepare
from chimeraforge.bench.fleet_trace_receipt import make_report
from chimeraforge.planner.replay import digest
from test_fleet_monitor import make_native_fleet
from test_fleet_trace import Node, Scene, endpoints, routes, workload

COMMON_CONTROLS = (
    "output_cap_tokens",
    "concurrency",
    "request_timeout_seconds",
    "trace_timeout_seconds",
    "cleanup_timeout_seconds",
    "targets",
    "replica_scope",
    "declared_original_replicas",
    "physical_independence",
)
PLAN_COMMITMENT = (
    "fingerprint",
    "raw_sha256",
    "candidate_index",
    "candidate_sha256",
    "served_model",
    "model_override",
)


@pytest.fixture(scope="module")
def template():
    saved, indices = make_native_fleet(tpot_slo=1000)
    index = indices["vllm"]
    requests = workload(saved, index)
    prepared = prepare(
        saved,
        requests,
        endpoints(),
        routes(requests),
        candidate_index=index,
        model=None,
        concurrency=3,
        request_timeout=300,
        trace_timeout=600,
        cleanup_timeout=2,
        stop_event=None,
    )

    class CachedNode(Node):
        def __init__(self, *args):
            super().__init__(*args)
            self.observed["prefix_cache"] = False

        async def generate_observed(self, *args):
            result = await super().generate_observed(*args)
            result.native["cached_prompt_tokens"] = 0
            return result

    async def execute():
        scene = Scene(saved, index)

        def backend(name, *, base_url, **kwargs):
            node = CachedNode(scene, name, base_url)
            scene.created.append(node)
            return node

        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(trace, "get_backend", backend)
            result = await api.replay_fleet_trace(
                saved, requests, endpoints(), routes(requests), candidate_index=index, concurrency=3
            )
        assert all(node.closed for node in scene.created)
        return result.to_dict()

    return prepared, asyncio.run(execute())


def synthetic(template, *, duration=0.1):
    prepared, initial = template
    rows = copy.deepcopy(initial["native_trace"]["requests"])
    for i, row in enumerate(rows):
        start = (i // prepared.plan.concurrency) * duration
        row["times"] = {
            "scheduled_s": 0,
            "arrival_s": 0,
            "start_s": start,
            "first_output_s": start + duration / 4,
            "terminal_s": start + duration,
        }
        row["mean_tpot_ms"] = duration * 0.75 * 1000 / (row["native"]["tokens_generated"] - 1)
        row["native"]["eval_duration_ms"] = duration * 0.75 * 1000
        row["native"]["throughput_tps"] = (row["native"]["tokens_generated"] - 1) / (
            duration * 0.75
        )
    elapsed = max(row["times"]["terminal_s"] for row in rows)
    native = trace._report(
        list(prepared.plan.requests),
        rows,
        workload=prepared.plan.workload,
        targets=prepared.plan.slos,
        model=prepared.plan.served_model,
        backend_name=prepared.plan.backend,
        base_url=None,
        concurrency=prepared.plan.concurrency,
        request_timeout=prepared.plan.request_timeout,
        trace_timeout=prepared.plan.trace_timeout,
        cleanup={"state": "completed"},
        observation={},
        stop_reason=None,
        error=None,
        elapsed=elapsed,
        origin=1000,
    )
    resources = copy.deepcopy(
        [
            {"before": row["serving_before"], "after": row["serving_after"], "error": None}
            for row in initial["slots"]
        ]
    )
    result = make_report(prepared, native, resources, copy.deepcopy(initial["cleanup"]))
    assert api.load_fleet_trace(result).to_dict() == result
    return result


@pytest.fixture(scope="module")
def single_template(template):
    saved = api.plan(
        api.PlanRequest(
            models=["ci/manual-fleet"],
            overrides={"params_b": 3.0, "n_layers": 28, "n_kv_heads": 8, "d_head": 128},
            hardware="RTX 4090 24GB",
            platform="linux",
            tensor_parallel=2,
            request_rate=10,
            latency_slo=10000,
            tpot_slo=1000,
            quality_target=0,
            budget=1e8,
            allow_network=False,
        )
    )
    index = next(
        i
        for i, row in enumerate(saved.to_dict()["result"]["candidates"])
        if row["backend"] == "vllm" and row["quant"] == "FP16" and row["n_agents"] == 1
    )
    requests = workload(saved, index)
    members = (api.FleetEndpoint("member-0", "http://member-0.invalid"),)
    mapping = [api.TraceRoute(row.request_id, "member-0") for row in requests]
    prepared = prepare(
        saved,
        requests,
        members,
        mapping,
        candidate_index=index,
        model=None,
        concurrency=3,
        request_timeout=300,
        trace_timeout=600,
        cleanup_timeout=2,
        stop_event=None,
    )
    three = synthetic(template)
    native = copy.deepcopy(three["native_trace"])
    for row in native["requests"]:
        row["endpoint_id"] = "member-0"
    native["fingerprint"] = digest({k: v for k, v in native.items() if k != "fingerprint"})
    slot = three["slots"][0]
    resources = [{"before": slot["serving_before"], "after": slot["serving_after"], "error": None}]
    cleanup = copy.deepcopy(three["cleanup"])
    tasks = 2 + 2 * len(requests) + 3
    cleanup.update(owned_backends=1, closed_backends=1, owned_tasks=tasks, joined_tasks=tasks)
    initial = make_report(prepared, native, resources, cleanup)
    assert api.load_fleet_trace(initial).to_dict() == initial
    return prepared, initial


@pytest.mark.parametrize("direction", ["three_to_one", "one_to_three"])
def test_valid_mismatched_populations_preserve_every_member_in_each_arm(
    template, single_template, direction
):
    before, after = (
        (template, single_template) if direction == "three_to_one" else (single_template, template)
    )
    left, right = synthetic(before), synthetic(after, duration=0.125)
    # The predeclared complete common population is valid; the other genuine input violates it.
    chosen = policy(left, left)
    chosen["population"]["original_replicas"] = len(left["slots"])
    chosen["population"]["controls"]["declared_original_replicas"] = len(left["slots"])
    result = api.gate_fleet_traces(left, right, policy=chosen).to_dict()
    assert result["exit_code"] == 3
    assert result["known_breaches"] == ["latency_p95_ms"]
    assert result["metrics"]["latency_p95_ms"]["regression_fraction"] == pytest.approx(0.25)
    for arm, original in (("baseline", left), ("candidate", right)):
        assert result["inputs"][arm]["slots"] == original["slots"]
        assert len(result["inputs"][arm]["slots"]) == len(original["endpoints"])


def policy(left, right, *, threshold=0.1, fixed=None):
    return {
        "trace": {
            "rules": {"latency_p95_ms": threshold},
            "fixed_controls": fixed or {},
            "require_cache_evidence": True,
        },
        "population": {
            "original_replicas": 3,
            "endpoint_ids": [row["id"] for row in left["endpoints"]],
            "workload_sha256": left["workload"]["canonical_sha256"],
            "ordered_descriptors_sha256": digest(
                [row["descriptor"] for row in left["native_trace"]["requests"]]
            ),
            "routes_sha256": left["routes"]["canonical_sha256"],
            "minimum_requests_per_slot": 1,
            "controls": {key: left["controls"][key] for key in COMMON_CONTROLS},
        },
        **{
            arm: {
                "plan": {key: value["plan"][key] for key in PLAN_COMMITMENT},
                "backend": value["controls"]["backend"],
                "endpoints": value["endpoints"],
            }
            for arm, value in (("baseline", left), ("candidate", right))
        },
    }


def rebuild(template, data):
    prepared, _ = template
    selected = data["plan"]["snapshot"]["result"]["candidates"][data["plan"]["candidate_index"]]
    plan = replace(
        prepared.plan,
        data=data["plan"]["snapshot"],
        candidate=selected,
        candidate_index=data["plan"]["candidate_index"],
        plan_raw_sha256=data["plan"]["raw_sha256"],
        workload=data["workload"],
        served_model=data["controls"]["model"],
        model_override=data["plan"]["model_override"],
        concurrency=data["controls"]["concurrency"],
        request_timeout=data["controls"]["request_timeout_seconds"],
        trace_timeout=data["controls"]["trace_timeout_seconds"],
    )
    prepared = replace(
        prepared,
        plan=plan,
        endpoints=tuple(api.FleetEndpoint(**row) for row in data["endpoints"]),
        routes=tuple(api.TraceRoute(**row) for row in data["routes"]["rows"]),
        route_identity={key: data["routes"][key] for key in ("canonical_sha256", "raw_sha256")},
        cleanup_timeout=data["controls"]["cleanup_timeout_seconds"],
    )
    old = data["native_trace"]
    native = trace._report(
        list(plan.requests),
        old["requests"],
        workload=plan.workload,
        targets=plan.slos,
        model=plan.served_model,
        backend_name=plan.backend,
        base_url=None,
        concurrency=plan.concurrency,
        request_timeout=plan.request_timeout,
        trace_timeout=plan.trace_timeout,
        cleanup={"state": data["cleanup"]["state"]},
        observation={},
        stop_reason=old["stop_reason"],
        error=old["error"],
        elapsed=old["execution"]["elapsed_seconds"],
        origin=old["clock"]["origin"],
    )
    resources = [
        {"before": row["serving_before"], "after": row["serving_after"], "error": row["error"]}
        for row in data["slots"]
    ]
    result = make_report(prepared, native, resources, data["cleanup"])
    assert api.load_fleet_trace(result).to_dict() == result
    return result


@pytest.mark.parametrize(
    "fault",
    ["backend_list", "private_key", "replicates", "boolean_n", "raw_wildcard", "missing_routes"],
)
def test_closed_policy_malformed_is_refusal(template, fault):
    left, right = synthetic(template), synthetic(template, duration=0.09)
    chosen = policy(left, right)
    if fault == "backend_list":
        chosen["baseline"]["backend"] = []
    elif fault == "private_key":
        chosen["PRIVATE-POLICY-CANARY"] = "must not echo"
    elif fault == "replicates":
        chosen["trace"]["expected_replicates"] = 3
    elif fault == "boolean_n":
        chosen["population"]["original_replicas"] = True
    elif fault == "raw_wildcard":
        del chosen["candidate"]["plan"]["raw_sha256"]
    else:
        del chosen["population"]["routes_sha256"]
    with pytest.raises(api.PlanError) as caught:
        api.gate_fleet_traces(left, right, policy=chosen)
    assert "PRIVATE" not in str(caught.value)


def test_declared_pair_budget_and_same_path_read_once(template, tmp_path, monkeypatch):
    from chimeraforge.bench import fleet_gate_inputs, fleet_trace_receipt

    value = synthetic(template)
    source = tmp_path / "same.json"
    raw = json.dumps(value).encode("utf-8")
    source.write_bytes(raw)
    reads = []
    original = fleet_trace_receipt.held_json

    def observed(source, limit):
        if isinstance(source, type(tmp_path)):
            reads.append(source)
        return original(source, limit)

    monkeypatch.setattr(fleet_trace_receipt, "held_json", observed)
    result = api.gate_fleet_traces(source, source, policy=policy(value, value)).to_dict()
    assert reads == [source]
    assert result["exit_code"] == 3 and "duplicate_execution_payload" in result["blockers"]
    assert (
        result["inputs"]["baseline"]["size_bytes"]
        == result["inputs"]["candidate"]["size_bytes"]
        == len(raw)
    )
    monkeypatch.setattr(fleet_gate_inputs, "MAX_TOTAL_BYTES", 2 * len(raw) - 1)
    with pytest.raises(api.PlanError):
        api.gate_fleet_traces(source, source, policy=policy(value, value))


@pytest.mark.parametrize("fault", ["source", "inactive", "partial", "cache", "drift", "cleanup"])
def test_all_adverse_populations_remain_inconclusive(template, fault):
    left, right = synthetic(template), synthetic(template, duration=0.125)
    chosen = policy(left, right)
    if fault == "source":
        snapshot = right["plan"]["snapshot"]
        snapshot["created_at"] = "2026-10-26T00:00:00+00:00"
        snapshot["fingerprint"] = digest({k: v for k, v in snapshot.items() if k != "fingerprint"})
        right["plan"]["fingerprint"] = snapshot["fingerprint"]
    elif fault == "inactive":
        for row, route in zip(right["native_trace"]["requests"], right["routes"]["rows"]):
            if row["endpoint_id"] == "member-2":
                row["endpoint_id"] = route["endpoint_id"] = "member-0"
        right["routes"]["canonical_sha256"] = digest(right["routes"]["rows"])
    elif fault == "partial":
        right["native_trace"]["requests"][-1].update(
            state="partial", error={"stage": "generation", "type": "HTTPError"}
        )
    elif fault == "cache":
        right["native_trace"]["requests"][0]["native"]["cached_prompt_tokens"] = 1
    elif fault == "drift":
        right["slots"][0]["serving_after"]["tensor_parallel"] = 1
    else:
        right["cleanup"].update(state="incomplete", allowance_exceeded=True)
        right["native_trace"]["error"] = {"stage": "cleanup", "type": "RuntimeError"}
    right = rebuild(template, right)
    result = api.gate_fleet_traces(left, right, policy=chosen).to_dict()
    assert result["exit_code"] == 3 and result["outcome"] == "inconclusive"
    assert len(result["members"]) == 3 and len(result["inputs"]["candidate"]["rows"]) == 6
    assert result["metrics"]["latency_p95_ms"]["state"] == "inconclusive"
    if fault == "partial":
        assert result["metrics"]["latency_p95_ms"]["candidate"] is None
        assert result["inputs"]["candidate"]["rows"][-1]["state"] == "partial"
    else:
        assert result["known_breaches"] == ["latency_p95_ms"]
    if fault == "inactive":
        assert result["members"][2]["cache"]["candidate"]["state"] == "unknown"


def test_goodput_cannot_drop_native_mean_basis_guard(template):
    left, right = synthetic(template), synthetic(template, duration=0.09)
    right["native_trace"]["requests"][0]["mean_tpot_basis"] = (
        "client-first-to-last-native-output/(server-output-count-1)"
    )
    right = rebuild(template, right)
    chosen = policy(left, right)
    chosen["trace"]["rules"] = {"goodput_rps": 0.1}
    result = api.gate_fleet_traces(left, right, policy=chosen).to_dict()
    assert result["exit_code"] == 3
    assert "mean_timing_basis_unavailable_or_changed" in result["blockers"]
    assert result["metrics"]["goodput_rps"]["baseline"] == pytest.approx(30)


@pytest.mark.parametrize("decoration", ["labels", "member_permutation", "reals_and_task_counts"])
def test_semantic_copies_cannot_become_executions_by_relabeling(template, decoration):
    left = synthetic(template)
    right = copy.deepcopy(left)
    chosen = policy(left, left)
    if decoration == "labels":
        names = {f"member-{i}": f"new-{i}" for i in range(3)}
        for i, (row, route) in enumerate(
            zip(right["native_trace"]["requests"], right["routes"]["rows"])
        ):
            row["descriptor"]["request_id"] = route["request_id"] = f"new-request-{i}"
            row["endpoint_id"] = route["endpoint_id"] = names[route["endpoint_id"]]
        for i, (endpoint, slot) in enumerate(zip(right["endpoints"], right["slots"])):
            endpoint["id"] = slot["id"] = names[endpoint["id"]]
            endpoint["url"] = slot["url"] = f"http://new-{i}.invalid"
        right["routes"]["canonical_sha256"] = digest(right["routes"]["rows"])
    elif decoration == "member_permutation":
        right["endpoints"].reverse()
        right["slots"].reverse()
    else:
        right["cleanup"]["owned_tasks"] += 1
        right["cleanup"]["joined_tasks"] += 1
        right["cleanup"]["budget_seconds"] = right["controls"]["cleanup_timeout_seconds"] = 2.0
        right["controls"]["request_timeout_seconds"] = 300.0
        right["controls"]["trace_timeout_seconds"] = 600.0
        for row in right["native_trace"]["requests"]:
            row["descriptor"]["arrival_offset_s"] = -0.0
            row["times"]["scheduled_s"] = row["times"]["arrival_s"] = -0.0
    right["native_trace"]["clock"]["origin"] = 99999
    right = rebuild(template, right)
    result = api.gate_fleet_traces(left, right, policy=chosen).to_dict()
    assert result["exit_code"] == 3 and "duplicate_execution_payload" in result["blockers"]


def test_complete_whole_fleet_conditional_gate(template):
    left, right = synthetic(template), synthetic(template, duration=0.09)
    chosen = policy(left, right)
    result = api.gate_fleet_traces(left, right, policy=api.FleetTraceGatePolicy(**chosen)).to_dict()
    assert result["outcome"] == "conditional_pass" and result["exit_code"] == 0
    assert result["population"]["baseline"]["original_replicas"] == 3
    assert len(result["members"]) == 3
    assert result["metrics"]["latency_p95_ms"]["baseline"] == pytest.approx(200)


def test_native_global_regression_and_strict_threshold_equality(template):
    left, right = synthetic(template), synthetic(template, duration=0.125)
    result = api.gate_fleet_traces(left, right, policy=policy(left, right)).to_dict()
    assert result["outcome"] == "regression" and result["exit_code"] == 1
    metric = result["metrics"]["latency_p95_ms"]
    assert metric["baseline"] == pytest.approx(200) and metric["candidate"] == pytest.approx(250)
    assert metric["regression_fraction"] == pytest.approx(0.25)
    equal = api.gate_fleet_traces(left, right, policy=policy(left, right, threshold=0.25)).to_dict()
    assert equal["exit_code"] == 0


def test_missing_required_member_evidence_precedes_known_arithmetic_breach(template):
    left, right = synthetic(template), synthetic(template, duration=0.125)
    result = api.gate_fleet_traces(
        left, right, policy=policy(left, right, fixed={"version": "different-required-version"})
    ).to_dict()
    assert result["outcome"] == "inconclusive" and result["exit_code"] == 3
    assert result["known_breaches"] == ["latency_p95_ms"]
    assert result["metrics"]["latency_p95_ms"]["regression_fraction"] == pytest.approx(0.25)


@pytest.mark.parametrize("outcome", [0, 1, 3])
def test_api_json_and_junit_serialize_the_same_final_decision(template, tmp_path, outcome):
    left = synthetic(template)
    right = synthetic(template, duration=0.09 if outcome == 0 else 0.125)
    chosen = policy(
        left, right, fixed={"version": "unavailable-required"} if outcome == 3 else None
    )
    result = api.gate_fleet_traces(left, right, policy=chosen)
    decision, junit = tmp_path / "decision.json", tmp_path / "result.xml"
    api.write_fleet_trace_gate(result, out=decision, junit=junit)
    assert json.loads(decision.read_bytes()) == result.to_dict()
    xml = ET.parse(junit).getroot()
    assert int(xml.attrib["tests"]) == 2 and len(xml.findall("testcase")) == 2
    assert len(xml.findall(".//failure")) == int(outcome == 1)
    assert len(xml.findall(".//error")) == (2 if outcome == 3 else 0)
    assert not xml.findall(".//skipped")
    assert b"PRIVATE" not in junit.read_bytes() and b"http:" not in junit.read_bytes()
    if outcome == 3:
        fraction = xml.find(
            ".//testcase[@name='latency_p95_ms']/properties/property[@name='regression_fraction']"
        )
        assert float(fraction.attrib["value"]) == pytest.approx(0.25)


def test_gate_cli_whole_arity_and_two_output_admission(template, tmp_path):
    from typer.testing import CliRunner
    from chimeraforge.cli import app

    left, right = synthetic(template), synthetic(template, duration=0.09)
    sources = [tmp_path / name for name in ("left.json", "right.json", "policy.json")]
    for path, value in zip(sources, (left, right, policy(left, right))):
        path.write_text(json.dumps(value), encoding="utf-8")
    decision, junit = tmp_path / "decision.json", tmp_path / "result.xml"
    args = [
        "gate",
        "--kind",
        "fleet-trace",
        "--baseline",
        str(sources[0]),
        "--candidate",
        str(sources[1]),
        "--policy",
        str(sources[2]),
        "--out",
        str(decision),
        "--junit",
        str(junit),
        "--json",
    ]
    runner = CliRunner()
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == json.loads(decision.read_bytes())
    assert ET.parse(junit).getroot().attrib["errors"] == "0"
    prior = decision.read_bytes()
    for changes in (
        ["--junit", str(decision)],
        ["--out", str(sources[0])],
        ["--junit", str(sources[2])],
        ["--baseline", str(sources[0])],
    ):
        refused = runner.invoke(app, args + changes)
        assert refused.exit_code == 2, refused.output
        assert decision.read_bytes() == prior


def test_junit_bounds_precede_either_write_and_late_fs_failure_is_not_a_transaction(
    template, tmp_path, monkeypatch
):
    from chimeraforge.bench import fleet_gate_output

    left, right = synthetic(template), synthetic(template, duration=0.09)
    result = api.gate_fleet_traces(left, right, policy=policy(left, right))
    decision, junit = tmp_path / "decision.json", tmp_path / "result.xml"
    decision.write_bytes(b"prior decision")
    junit.write_bytes(b"prior junit")
    with monkeypatch.context() as patch:
        patch.setattr(fleet_gate_output, "MAX_JUNIT_BYTES", 4)
        with pytest.raises(api.PlanError):
            api.write_fleet_trace_gate(result, out=decision, junit=junit)
        assert decision.read_bytes() == b"prior decision" and junit.read_bytes() == b"prior junit"
    original = Path.replace

    def fail_second(source, target):
        if Path(target) == junit:
            raise OSError("PRIVATE FILESYSTEM CANARY")
        return original(source, target)

    monkeypatch.setattr(Path, "replace", fail_second)
    with pytest.raises(api.PlanError):
        api.write_fleet_trace_gate(result, out=decision, junit=junit)
    assert json.loads(decision.read_bytes()) == result.to_dict()
    assert junit.read_bytes() == b"prior junit" and not list(tmp_path.glob("*.tmp"))


def test_installed_gate_consumer_runs_actual_api_cli_and_junit(template, tmp_path, monkeypatch):
    from test_ci_acceptance import load_script
    from typer.testing import CliRunner
    from chimeraforge.cli import app

    script = load_script("ci_fleet_trace_gate")
    parent = load_script("ci_installed_acceptance")
    calls = []

    def source_cli(arguments, cwd, env, expected_code=0):
        result = CliRunner().invoke(app, arguments, env=env)
        assert result.exit_code == expected_code, result.output
        calls.append(expected_code)
        return result.stdout

    monkeypatch.setattr(parent, "run_cli", source_cli)
    saved = tmp_path / "plan.json"
    saved.write_text(json.dumps(template[0].plan.data), encoding="utf-8")
    result = script.accept(tmp_path, {}, saved)
    assert [row["api_exit"] for row in result["controls"]] == [0, 1, 3]
    assert [row["cli_exit"] for row in result["controls"]] == [0, 1, 3]
    assert calls[:3] == [0, 1, 3] and calls[3:] == [2, 2]
    assert result["input_bytes_unchanged"] and result["synthetic"] is True


def test_cpu_report_consumer_keeps_known_mismatch_inconclusive_without_new_traffic(
    template, tmp_path, monkeypatch
):
    from test_ci_acceptance import load_script
    from typer.testing import CliRunner
    from chimeraforge.cli import app

    script = load_script("ci_fleet_trace_gate")
    parent = load_script("ci_installed_acceptance")
    left, right = synthetic(template), synthetic(template, duration=0.125)
    for data in (left, right):
        for slot in data["slots"]:
            for phase in ("serving_before", "serving_after"):
                slot[phase]["quant"] = "Q8_0"
    left, right = rebuild(template, left), rebuild(template, right)
    assert left["exit_code"] == right["exit_code"] == 1

    def source_cli(arguments, cwd, env, expected_code=0):
        result = CliRunner().invoke(app, arguments, env=env)
        assert result.exit_code == expected_code, result.output
        return result.stdout

    monkeypatch.setattr(parent, "run_cli", source_cli)
    result = script.accept_native(tmp_path, {}, left, right)
    assert result["api_exit"] == result["cli_exit"] == 3 and result["junit_errors"] == 2
    assert result["known_breaches"] == ["latency_p95_ms"]


def test_held_outer_identity_and_inherited_source_paths_are_not_native_projection_identity(
    template, tmp_path
):
    import hashlib
    import os
    from chimeraforge.bench.fleet_trace_types import FleetTraceReplay

    left, right = synthetic(template), synthetic(template, duration=0.09)
    source = tmp_path / "receipt.json"
    raw = (json.dumps(left, indent=1) + "\n").encode("utf-8")
    source.write_bytes(raw)
    file_result = api.gate_fleet_traces(source, right, policy=policy(left, right)).to_dict()
    held = file_result["inputs"]["baseline"]
    assert held["sha256"] == hashlib.sha256(raw).hexdigest() and held["size_bytes"] == len(raw)
    assert file_result["exit_code"] == 0
    inputs = [tmp_path / name for name in ("saved.json", "work.json", "routes.json")]
    for path in inputs:
        path.write_bytes(b"held input")
    typed = FleetTraceReplay(left, tuple(inputs))
    result = api.gate_fleet_traces(typed, right, policy=policy(left, right))
    assert result.to_dict()["metrics"] == file_result["metrics"]
    for path in inputs:
        with pytest.raises(api.PlanError):
            api.write_fleet_trace_gate(result, junit=path)
        assert path.read_bytes() == b"held input"
    linked = tmp_path / "hardlink.xml"
    os.link(inputs[0], linked)
    with pytest.raises(api.PlanError):
        api.write_fleet_trace_gate(result, junit=linked)
    output = tmp_path / "decision.json"
    output.write_bytes(b"prior decision")
    linked_output = tmp_path / "decision-alias.xml"
    os.link(output, linked_output)
    with pytest.raises(api.PlanError):
        api.write_fleet_trace_gate(result, out=output, junit=linked_output)
    assert output.read_bytes() == b"prior decision"


def test_zero_baseline_remains_unavailable_and_cannot_be_divided(template):
    left, right = synthetic(template), synthetic(template, duration=0.09)
    for row in left["native_trace"]["requests"]:
        row["times"]["first_output_s"] = row["times"]["start_s"]
    left = rebuild(template, left)
    chosen = policy(left, right)
    chosen["trace"]["rules"] = {"first_output_p95_ms": 0.1}
    # Later queued rows still have queueing latency: use concurrency=6 in BOTH native declarations.
    for data in (left, right):
        data["controls"]["concurrency"] = data["native_trace"]["execution"]["concurrency"] = 6
        for row in data["native_trace"]["requests"]:
            start = row["times"]["start_s"]
            for name in ("start_s", "first_output_s", "terminal_s"):
                row["times"][name] -= start
        data["native_trace"]["execution"]["elapsed_seconds"] = max(
            row["times"]["terminal_s"] for row in data["native_trace"]["requests"]
        )
    left, right = rebuild(template, left), rebuild(template, right)
    chosen = policy(left, right)
    chosen["trace"]["rules"] = {"first_output_p95_ms": 0.1}
    result = api.gate_fleet_traces(left, right, policy=chosen).to_dict()
    assert result["exit_code"] == 3
    metric = result["metrics"]["first_output_p95_ms"]
    assert metric["baseline"] == 0 and metric["regression_fraction"] is None


def test_closed_policy_cannot_reference_an_unheld_nested_policy_file(template, tmp_path):
    left, right = synthetic(template), synthetic(template, duration=0.09)
    chosen = policy(left, right)
    nested = tmp_path / "nested.json"
    nested.write_text(json.dumps(chosen["trace"]), encoding="utf-8")
    chosen["trace"] = str(nested)
    with pytest.raises(api.PlanError):
        api.gate_fleet_traces(left, right, policy=chosen)


def test_writer_refuses_incoherent_finalized_states_before_clobber(template, tmp_path):
    from chimeraforge.bench.gate import RegressionGate

    left, right = synthetic(template), synthetic(template, duration=0.09)
    data = api.gate_fleet_traces(left, right, policy=policy(left, right)).to_dict()
    data["metrics"]["latency_p95_ms"]["state"] = "regression"
    data["fingerprint"] = digest({k: v for k, v in data.items() if k != "fingerprint"})
    target = tmp_path / "prior.xml"
    target.write_bytes(b"prior")
    with pytest.raises(api.PlanError):
        api.write_fleet_trace_gate(RegressionGate(data), junit=target)
    assert target.read_bytes() == b"prior"


@pytest.mark.parametrize(
    "cleanup_operation,primary_failure", [("exists", True), ("unlink", True), ("exists", False)]
)
def test_output_cleanup_error_cannot_escape_or_disclose_primary_filesystem_error(
    template, tmp_path, monkeypatch, caplog, cleanup_operation, primary_failure
):
    left, right = synthetic(template), synthetic(template, duration=0.09)
    result = api.gate_fleet_traces(left, right, policy=policy(left, right))
    target = tmp_path / "decision.json"
    target.write_bytes(b"prior")
    original_exists, original_unlink, original_replace = Path.exists, Path.unlink, Path.replace

    def replace_failed(source, target):
        if primary_failure:
            raise OSError("PRIVATE PRIMARY FILESYSTEM")
        return original_replace(source, target)

    def cleanup_failed(path, *args, **kwargs):
        if path.suffix == ".tmp":
            raise PermissionError("PRIVATE TEMP CLEANUP")
        return (original_exists if cleanup_operation == "exists" else original_unlink)(
            path, *args, **kwargs
        )

    try:
        with monkeypatch.context() as patch:
            patch.setattr(Path, "replace", replace_failed)
            patch.setattr(Path, cleanup_operation, cleanup_failed)
            with pytest.raises(api.PlanError) as error:
                api.write_fleet_trace_gate(result, out=target)
            assert "PRIVATE" not in str(error.value) and "PRIVATE" not in caplog.text
            assert ("output could not be written" in str(error.value)) is primary_failure
    finally:
        for path in tmp_path.glob("*.tmp"):
            original_unlink(path)
    if primary_failure:
        assert target.read_bytes() == b"prior"
    else:
        assert json.loads(target.read_bytes()) == result.to_dict()
