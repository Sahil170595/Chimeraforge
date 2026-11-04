"""Closed campaign receiving preserves every native execution and declared slot."""

from __future__ import annotations

import copy

import pytest

from chimeraforge import api
from chimeraforge.bench.fleet_campaign_types import canonical_hash
from test_fleet_trace import endpoints, routes, workload
import test_fleet_trace as native_fleet_trace
import test_fleet_trace_gate as native_gate
from chimeraforge.bench.fleet_campaign import manifest_for
from chimeraforge.bench.fleet_campaign_types import CAMPAIGN_LIMITS, KIND

native_fleet = native_fleet_trace.native_fleet
scene = native_fleet_trace.scene
fleet_template = native_gate.template


async def campaign(native_fleet):
    saved, indices = native_fleet
    requests = workload(saved, indices["vllm"])
    return await api.replay_fleet_trace_campaign(
        saved,
        requests,
        endpoints(),
        routes(requests),
        executions=2,
        candidate_index=indices["vllm"],
    )


@pytest.mark.asyncio
async def test_public_receiving_rederives_every_original_execution(native_fleet, scene):
    report = await campaign(native_fleet)
    loaded = api.load_fleet_trace_campaign(report)
    assert loaded.to_dict() == report.to_dict()
    assert len(loaded.to_dict()["executions"]) == 2
    assert all(len(slot["receipt"]["slots"]) == 3 for slot in loaded.to_dict()["executions"])


@pytest.mark.parametrize(
    "change", ["count", "clock", "missing", "route", "completion", "producer", "scope"]
)
@pytest.mark.asyncio
async def test_receiving_refuses_recomputed_fingerprint_tampering(native_fleet, scene, change):
    data = (await campaign(native_fleet)).to_dict()
    if change == "count":
        data["execution"]["completed"] = float(data["execution"]["completed"])
    elif change == "clock":
        data["executions"][1]["start_s"] = data["executions"][0]["start_s"]
    elif change == "missing":
        data["executions"].pop()
    elif change == "route":
        data["manifest"]["routes"]["rows"][0]["endpoint_id"] = "member-1"
        data["manifest"]["fingerprint"] = canonical_hash(
            {k: v for k, v in data["manifest"].items() if k != "fingerprint"}
        )
        for slot in data["executions"]:
            slot["manifest_fingerprint"] = data["manifest"]["fingerprint"]
    elif change == "completion":
        data["executions"][0]["execution_complete"] = 1
    elif change == "producer":
        data["tool"]["version"] += "-changed"
    else:
        data["limits"] = "Physical independence verified"
    data["fingerprint"] = canonical_hash({k: v for k, v in data.items() if k != "fingerprint"})
    with pytest.raises(api.PlanError):
        api.load_fleet_trace_campaign(copy.deepcopy(data))


def synthetic_campaign(template, durations):
    """Native pure report builders over controlled timings; not real serving trials."""
    prepared, _ = template
    manifest = manifest_for(prepared, len(durations), 1800)
    slots = []
    for index, duration in enumerate(durations):
        child = native_gate.synthetic(template, duration=duration)
        child["native_trace"]["clock"]["origin"] = 1000 + 10 * index
        child["native_trace"]["fingerprint"] = canonical_hash(
            {k: v for k, v in child["native_trace"].items() if k != "fingerprint"}
        )
        child["fingerprint"] = canonical_hash(
            {k: v for k, v in child.items() if k != "fingerprint"}
        )
        elapsed = child["native_trace"]["execution"]["elapsed_seconds"]
        slots.append(
            {
                "index": index,
                "manifest_fingerprint": manifest["fingerprint"],
                "state": "completed",
                "execution_complete": True,
                "reason": None,
                "error": None,
                "start_s": 1 + 10 * index,
                "end_s": 1 + 10 * index + elapsed + 0.01,
                "receipt": child,
            }
        )
    data = {
        "schema_version": 1,
        "kind": KIND,
        "created_at": slots[0]["receipt"]["created_at"],
        "tool": manifest["tool"],
        "manifest": manifest,
        "executions": slots,
        "execution": {
            "planned": len(slots),
            "completed": len(slots),
            "incomplete": 0,
            "failed": 0,
            "not_started": 0,
        },
        "clock": {
            "basis": "client time.perf_counter monotonic offsets in seconds",
            "origin": 999,
            "elapsed_seconds": slots[-1]["end_s"] + 0.01,
        },
        "stop_reason": None,
        "state": "completed",
        "configuration_status": "unverified",
        "exit_code": 0,
        "cleanup": {
            "state": "completed",
            "owned_children": len(slots),
            "joined_children": len(slots),
            "owned_waiters": 0,
            "joined_waiters": 0,
        },
        "limits": CAMPAIGN_LIMITS,
    }
    data["fingerprint"] = canonical_hash(data)
    assert api.load_fleet_trace_campaign(data).to_dict() == data
    return data


def campaign_policy(left, right):
    return {
        "schema_version": 1,
        "expected_executions": 2,
        "campaign_timeout_seconds": 1800,
        "fleet": native_gate.policy(
            left["executions"][0]["receipt"], right["executions"][0]["receipt"], threshold=0.1
        ),
    }


@pytest.mark.parametrize("outcome", [0, 1, 3])
def test_campaign_gate_uses_every_native_execution_and_complete_junit(
    fleet_template, tmp_path, outcome
):
    import xml.etree.ElementTree as ET

    left = synthetic_campaign(fleet_template, [0.1, 0.11])
    right = synthetic_campaign(fleet_template, [0.105, 0.115] if outcome != 1 else [0.2, 0.22])
    if outcome == 3:
        # A semantic duplicate within one arm is still duplicate evidence.
        right = synthetic_campaign(fleet_template, [0.105, 0.105])
    result = api.gate_fleet_trace_campaigns(left, right, policy=campaign_policy(left, right))
    data = result.to_dict()
    assert data["exit_code"] == outcome
    assert len(data["pairs"]) == 2 and all(len(pair["members"]) == 3 for pair in data["pairs"])
    assert all(len(data["inputs"][arm]["executions"]) == 2 for arm in ("baseline", "candidate"))
    target = tmp_path / "campaign.xml"
    api.write_fleet_trace_campaign_gate(result, junit=target)
    suite = ET.fromstring(target.read_bytes())
    assert int(suite.attrib["tests"]) == 5
    assert (int(suite.attrib["errors"]) == 5) if outcome == 3 else not int(suite.attrib["errors"])
    assert bool(int(suite.attrib["failures"])) == (outcome == 1)


def test_campaign_gate_cli_is_a_complete_byte_receiving_path(fleet_template, tmp_path):
    import json
    from typer.testing import CliRunner
    from chimeraforge.cli import app

    left = synthetic_campaign(fleet_template, [0.1, 0.11])
    right = synthetic_campaign(fleet_template, [0.105, 0.115])
    for name, value in (("left", left), ("right", right), ("policy", campaign_policy(left, right))):
        (tmp_path / (name + ".json")).write_text(json.dumps(value), encoding="utf-8")
    result = CliRunner().invoke(
        app,
        [
            "gate",
            "--kind",
            "fleet-trace-campaign",
            "--baseline",
            str(tmp_path / "left.json"),
            "--candidate",
            str(tmp_path / "right.json"),
            "--policy",
            str(tmp_path / "policy.json"),
            "--out",
            str(tmp_path / "decision.json"),
            "--junit",
            str(tmp_path / "decision.xml"),
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["exit_code"] == 0
    assert (tmp_path / "decision.xml").exists()


def test_campaign_cli_holds_inputs_once_and_rechecks_output_alias(native_fleet, scene, tmp_path):
    from dataclasses import asdict
    import json
    from typer.testing import CliRunner
    from chimeraforge.cli import app

    saved, indices = native_fleet
    requests = workload(saved, indices["vllm"])
    source, work, mapping = (
        tmp_path / name for name in ("source.json", "work.json", "routes.json")
    )
    saved.save(source)
    work.write_text(json.dumps([asdict(row) for row in requests]), encoding="utf-8")
    mapping.write_text(json.dumps([asdict(row) for row in routes(requests)]), encoding="utf-8")
    argv = [
        "trace-fleet-campaign",
        str(work),
        "--from-plan",
        str(source),
        "--routes",
        str(mapping),
        "--candidate-index",
        str(indices["vllm"]),
        "--executions",
        "2",
        "--json",
    ]
    for endpoint in endpoints():
        argv.extend(["--endpoint", endpoint.id + "=" + endpoint.url])
    original = work.read_bytes()
    refused = CliRunner().invoke(app, [*argv, "--out", str(work)])
    assert refused.exit_code == 2 and work.read_bytes() == original
    assert not scene.created
    result = CliRunner().invoke(app, argv)
    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)
    assert data["execution"]["completed"] == 2 and len(scene.created) == 6
    assert all(node.closed for node in scene.created)
    assert work.read_bytes() == original


@pytest.mark.asyncio
async def test_raw_and_canonical_new_profile_align_at_exact_limit(
    native_fleet, scene, tmp_path, monkeypatch
):
    import json
    from chimeraforge.bench import fleet_campaign_receipt

    report = await campaign(native_fleet)
    pretty = report.json_bytes()
    compact = json.dumps(report._data, separators=(",", ":")).encode()
    assert len(compact) < len(pretty) - 1
    source = tmp_path / "compact.json"
    source.write_bytes(compact)
    monkeypatch.setattr(fleet_campaign_receipt, "MAX_CAMPAIGN_BYTES", len(pretty))
    loaded = api.load_fleet_trace_campaign(source)
    assert loaded.json_bytes() == pretty
    monkeypatch.setattr(fleet_campaign_receipt, "MAX_CAMPAIGN_BYTES", len(pretty) - 1)
    for value in (source, loaded):
        with pytest.raises(api.PlanError):
            api.load_fleet_trace_campaign(value)


@pytest.mark.asyncio
async def test_full_typed_outcomes_survive_export_refusal_without_clobber(
    native_fleet, scene, tmp_path, monkeypatch
):
    from chimeraforge.bench import fleet_campaign_types

    report = await campaign(native_fleet)
    size = len(report.json_bytes())
    target = tmp_path / "existing.json"
    target.write_bytes(b"existing")
    monkeypatch.setattr(fleet_campaign_types, "MAX_CAMPAIGN_BYTES", size - 1)
    assert report.exit_code == 0 and report.state == "completed"
    assert len(report._data["executions"]) == 2
    with pytest.raises(api.FleetTraceCampaignError):
        report.save(target)
    assert target.read_bytes() == b"existing"


def test_gate_invalid_typed_policy_is_categorical_not_attribute_error(fleet_template):
    left = synthetic_campaign(fleet_template, [0.1, 0.11])
    right = synthetic_campaign(fleet_template, [0.105, 0.115])
    bad = api.FleetTraceCampaignGatePolicy(object(), 2, 1800)
    with pytest.raises(api.PlanError):
        api.gate_fleet_trace_campaigns(left, right, policy=bad)


def refresh_campaign(data):
    manifest = data["manifest"]
    manifest["fingerprint"] = canonical_hash(
        {k: v for k, v in manifest.items() if k != "fingerprint"}
    )
    for slot in data["executions"]:
        slot["manifest_fingerprint"] = manifest["fingerprint"]
    data["fingerprint"] = canonical_hash({k: v for k, v in data.items() if k != "fingerprint"})


@pytest.mark.parametrize("change", ["cap", "arrival"])
@pytest.mark.asyncio
async def test_all_unstarted_manifest_still_requires_native_request_controls(
    native_fleet, scene, change
):
    import asyncio

    saved, indices = native_fleet
    requests = workload(saved, indices["vllm"])
    stopped = asyncio.Event()
    stopped.set()
    original = await api.replay_fleet_trace_campaign(
        saved,
        requests,
        endpoints(),
        routes(requests),
        executions=2,
        candidate_index=indices["vllm"],
        stop_event=stopped,
    )
    data = api.load_fleet_trace_campaign(original).to_dict()
    assert all(slot["receipt"] is None for slot in data["executions"]) and not scene.created
    descriptor = data["manifest"]["ordered_descriptors"][0]
    if change == "cap":
        descriptor["max_output_tokens"] -= 1
    else:
        descriptor["arrival_offset_s"] = data["manifest"]["controls"]["trace_timeout_seconds"] + 1
    refresh_campaign(data)
    with pytest.raises(api.PlanError):
        api.load_fleet_trace_campaign(data)


@pytest.mark.asyncio
async def test_k_work_admission_preserves_exact_boundary_before_contact(native_fleet, scene):
    import asyncio

    saved, indices = native_fleet
    cap = saved.candidate(indices["vllm"]).decode_tokens_per_req
    requests = [api.TraceRequest(f"bound-{i}", "fixture", cap, 0) for i in range(256)]
    stopped = asyncio.Event()
    stopped.set()
    result = await api.replay_fleet_trace_campaign(
        saved,
        requests,
        endpoints(),
        routes(requests),
        executions=16,
        candidate_index=indices["vllm"],
        stop_event=stopped,
    )
    data = api.load_fleet_trace_campaign(result).to_dict()
    assert data["manifest"]["population"]["total_requests"] == 4096
    assert data["execution"]["not_started"] == 16
    requests.append(api.TraceRequest("bound-256", "fixture", cap, 0))
    with pytest.raises(api.PlanError):
        await api.replay_fleet_trace_campaign(
            saved,
            requests,
            endpoints(),
            routes(requests),
            executions=16,
            candidate_index=indices["vllm"],
            stop_event=stopped,
        )
    assert not scene.created


@pytest.mark.asyncio
async def test_native_and_loaded_carriers_keep_private_guards_outside_dataclass_data(
    native_fleet, scene, tmp_path
):
    from dataclasses import asdict, fields, replace
    from copy import copy
    import json

    report = await campaign(native_fleet)
    source = tmp_path / "received.json"
    report.save(source)
    original = source.read_bytes()
    loaded = api.load_fleet_trace_campaign(source)
    for value in (loaded, copy(loaded), replace(loaded)):
        assert [field.name for field in fields(value)] == ["_data"]
        text = json.dumps(asdict(value))
        assert "_protected_paths" not in text and "_received_raw" not in text
        assert str(source) not in text
        assert value._input_paths == loaded._input_paths
        with pytest.raises(api.PlanError):
            value.save(source)
        assert source.read_bytes() == original
    assert json.dumps(asdict(report))


def test_maximum_k_all_metrics_has_complete_bounded_junit(fleet_template, tmp_path):
    import xml.etree.ElementTree as ET
    from chimeraforge.bench.trace_gate import RULES

    left = synthetic_campaign(fleet_template, [0.1 + i / 1000 for i in range(16)])
    right = synthetic_campaign(fleet_template, [0.1004 + i / 1000 for i in range(16)])
    policy = campaign_policy(left, right)
    policy["expected_executions"] = 16
    policy["fleet"]["trace"]["rules"] = {name: 0.1 for name in RULES}
    result = api.gate_fleet_trace_campaigns(left, right, policy=policy)
    target = tmp_path / "maximum.xml"
    api.write_fleet_trace_campaign_gate(result, junit=target)
    assert len(target.read_bytes()) <= 64 * 1024
    assert int(ET.fromstring(target.read_bytes()).attrib["tests"]) == 81
    assert len(result.to_dict()["pairs"]) == 16


def test_missing_policy_slots_preserve_known_arithmetic_and_all_actual_cases(
    fleet_template, tmp_path
):
    import xml.etree.ElementTree as ET

    left = synthetic_campaign(fleet_template, [0.1, 0.11, 0.12])
    right = synthetic_campaign(fleet_template, [0.2, 0.22])
    policy = campaign_policy(left, right)
    policy["expected_executions"] = 4
    result = api.gate_fleet_trace_campaigns(left, right, policy=policy)
    data = result.to_dict()
    assert result.exit_code == 3 and data["known_breaches"]
    assert len(data["pairs"]) == 4
    assert len(data["inputs"]["baseline"]["executions"]) == 3
    assert len(data["inputs"]["candidate"]["executions"]) == 2
    assert data["pairs"][0]["metrics"]["latency_p95_ms"]["regression_fraction"] > 0.1
    target = tmp_path / "incomplete.xml"
    api.write_fleet_trace_campaign_gate(result, junit=target)
    suite = ET.fromstring(target.read_bytes())
    assert suite.attrib["tests"] == suite.attrib["errors"] == "9"
    assert suite.attrib["failures"] == "0"


@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["not_started", "failed", "incomplete"])
async def test_public_receiver_keeps_null_and_incomplete_execution_slots(
    native_fleet, scene, monkeypatch, state
):
    import asyncio
    from chimeraforge.bench import fleet_trace_types

    saved, indices = native_fleet
    requests = workload(saved, indices["vllm"])
    stop = asyncio.Event()
    if state == "not_started":
        stop.set()
    elif state == "failed":
        monkeypatch.setattr(fleet_trace_types, "MAX_FLEET_RECEIPT_BYTES", 128)
    else:
        scene.preflight_failure = endpoints()[0].url
    report = await api.replay_fleet_trace_campaign(
        saved,
        requests,
        endpoints(),
        routes(requests),
        executions=3,
        candidate_index=indices["vllm"],
        stop_event=stop,
    )
    # The lowered producer guard is restored before independently receiving returned data.
    monkeypatch.undo()
    data = api.load_fleet_trace_campaign(report).to_dict()
    assert len(data["executions"]) == 3 and data["executions"][0]["state"] == state
    assert all(
        slot["state"] == "not_started" and slot["receipt"] is None
        for slot in data["executions"][1:]
    )
    assert data["executions"][0]["execution_complete"] is (False if state == "incomplete" else None)
    assert all(node.closed for node in scene.created)


def test_gate_preflights_both_outputs_and_all_held_aliases(fleet_template, tmp_path, monkeypatch):
    import json
    import os
    from chimeraforge.bench import fleet_campaign_output
    from dataclasses import asdict, replace
    from copy import copy

    left = synthetic_campaign(fleet_template, [0.1, 0.11])
    right = synthetic_campaign(fleet_template, [0.105, 0.115])
    inputs = [tmp_path / name for name in ("baseline.json", "candidate.json", "policy.json")]
    for path, data in zip(inputs, (left, right, campaign_policy(left, right))):
        path.write_text(json.dumps(data), encoding="utf-8")
    held = {path: path.read_bytes() for path in inputs}
    result = api.gate_fleet_trace_campaigns(*inputs[:2], policy=inputs[2])
    for value in (result, copy(result), replace(result)):
        assert "_protected_paths" not in asdict(value)
        assert value._input_paths == result._input_paths
    other = tmp_path / "other.xml"
    other.write_bytes(b"unchanged")
    for path in inputs:
        with pytest.raises(api.PlanError):
            api.write_fleet_trace_campaign_gate(result, out=path, junit=other)
        assert other.read_bytes() == b"unchanged" and path.read_bytes() == held[path]
    alias = tmp_path / "hardlink.json"
    os.link(inputs[0], alias)
    with pytest.raises(api.PlanError):
        api.write_fleet_trace_campaign_gate(result, out=alias, junit=other)
    with pytest.raises(api.PlanError):
        api.write_fleet_trace_campaign_gate(result, out=other, junit=other)
    assert other.read_bytes() == b"unchanged"
    monkeypatch.setattr(fleet_campaign_output, "MAX_JUNIT_BYTES", 1)
    with pytest.raises(api.PlanError):
        api.write_fleet_trace_campaign_gate(result, out=tmp_path / "new.json", junit=other)
    assert not (tmp_path / "new.json").exists() and other.read_bytes() == b"unchanged"


@pytest.mark.parametrize("position", ["at", "after"])
def test_receiving_refuses_started_execution_at_or_after_campaign_deadline(
    fleet_template, position
):
    import math

    data = synthetic_campaign(fleet_template, [0.1])
    data["clock"]["origin"] -= 1
    data["clock"]["elapsed_seconds"] += 1
    slot = data["executions"][0]
    slot["start_s"] += 1
    slot["end_s"] += 1
    slot["reason"] = data["stop_reason"] = "campaign_deadline"
    data["state"], data["exit_code"] = "incomplete", 1
    # Native absolute clocks are unchanged. A late completion remains admissible
    # when its start is one representable value before the declared deadline.
    data["manifest"]["controls"]["campaign_timeout_seconds"] = math.nextafter(
        slot["start_s"], math.inf
    )
    refresh_campaign(data)
    assert (
        api.load_fleet_trace_campaign(data).to_dict()["executions"][0]["execution_complete"] is True
    )
    data["manifest"]["controls"]["campaign_timeout_seconds"] = (
        slot["start_s"] if position == "at" else math.nextafter(slot["start_s"], 0)
    )
    refresh_campaign(data)
    with pytest.raises(api.PlanError):
        api.load_fleet_trace_campaign(data)


@pytest.mark.parametrize("reason", ["caller_stop", "campaign_deadline"])
@pytest.mark.parametrize("entry", ["load", "gate"])
def test_retained_terminal_stop_cannot_be_ignored_by_receiving_or_gate(
    fleet_template, reason, entry
):
    left = synthetic_campaign(fleet_template, [0.1, 0.11])
    right = synthetic_campaign(fleet_template, [0.105, 0.115])
    policy = campaign_policy(left, right)
    assert api.gate_fleet_trace_campaigns(left, right, policy=policy).exit_code == 0
    right["executions"][-1]["reason"] = reason
    refresh_campaign(right)
    with pytest.raises(api.PlanError):
        accepted = (
            api.load_fleet_trace_campaign(right)
            if entry == "load"
            else api.gate_fleet_trace_campaigns(left, right, policy=policy)
        )
        print("unexpected accepted terminal-stop", entry, reason, "exit_code", accepted.exit_code)


@pytest.mark.asyncio
@pytest.mark.parametrize("reason", ["first_incomplete_execution", "native_receipt_unavailable"])
async def test_all_unstarted_cannot_claim_a_nonexistent_native_failure(native_fleet, scene, reason):
    import asyncio

    saved, indices = native_fleet
    requests = workload(saved, indices["vllm"])
    stopped = asyncio.Event()
    stopped.set()
    report = await api.replay_fleet_trace_campaign(
        saved,
        requests,
        endpoints(),
        routes(requests),
        candidate_index=indices["vllm"],
        executions=2,
        stop_event=stopped,
    )
    data = api.load_fleet_trace_campaign(report).to_dict()
    data["stop_reason"] = reason
    for slot in data["executions"]:
        slot["reason"] = reason
    refresh_campaign(data)
    assert not scene.created
    with pytest.raises(api.PlanError):
        api.load_fleet_trace_campaign(data)
