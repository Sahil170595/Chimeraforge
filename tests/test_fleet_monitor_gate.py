"""Whole-original-fleet eligibility precedes passive candidate SLO acceptance."""

from __future__ import annotations

import copy
import json
from xml.etree import ElementTree as ET

import pytest
from typer.testing import CliRunner

from chimeraforge import api
from chimeraforge.cli import app
import test_fleet_monitor_receipt as native_receipts

assembled_report = native_receipts.assembled_report
monitor_source = native_receipts.monitor_source
monitor_source_one = native_receipts.monitor_source_one
monitor_source_sixteen = native_receipts.monitor_source_sixteen


def policy_for(baseline, candidate):
    return {
        "schema_version": 1,
        "original_replicas": len(baseline.slots),
        "endpoint_ids": [row.id for row in baseline.slots],
        "windows": 4,
        "metrics": {"ttft": {"minimum_samples": 20}},
        **{
            arm: {
                "plan": {
                    "fingerprint": report.plan["fingerprint"],
                    "candidate_index": report.plan["candidate_index"],
                },
                "controls": copy.deepcopy(report.effective_controls),
            }
            for arm, report in (("baseline", baseline), ("candidate", candidate))
        },
    }


def test_complete_passive_gate_cli_produces_all_declared_junit_cases(monitor_source, tmp_path):
    baseline = assembled_report(monitor_source, version_chars=32)
    candidate = assembled_report(monitor_source, version_chars=32, seconds=2)
    saved, _ = monitor_source
    source, left, right, policy = (
        tmp_path / name for name in ("plan.json", "left.json", "right.json", "policy.json")
    )
    saved.save(source)
    baseline.save(left)
    candidate.save(right)
    policy.write_text(json.dumps(policy_for(baseline, candidate)), encoding="utf-8")
    out, junit = tmp_path / "gate.json", tmp_path / "gate.xml"
    result = CliRunner().invoke(
        app,
        [
            "gate",
            "--kind",
            "fleet-monitor",
            "--baseline",
            str(left),
            "--candidate",
            str(right),
            "--baseline-plan",
            str(source),
            "--candidate-plan",
            str(source),
            "--policy",
            str(policy),
            "--out",
            str(out),
            "--junit",
            str(junit),
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    decision = json.loads(result.stdout)
    assert decision["exit_code"] == 0 and len(decision["cases"]) == 24
    suite = ET.fromstring(junit.read_bytes())
    assert suite.attrib["tests"] == "25" and suite.attrib["errors"] == "0"
    assert json.loads(out.read_bytes()) == decision


@pytest.mark.parametrize("fault", ["copy", "legacy", "samples", "stale", "configuration"])
def test_ineligible_whole_population_cannot_pass(monitor_source, fault):
    from chimeraforge.fleet_monitor_types import FleetMonitorReport
    from chimeraforge.monitor_binding import assemble_binding
    from chimeraforge.monitor import MonitorRequest

    baseline = assembled_report(monitor_source, version_chars=32)
    candidate = assembled_report(monitor_source, version_chars=32, seconds=2)
    saved, indices = monitor_source
    policy = policy_for(baseline, candidate)
    if fault == "copy":
        candidate = copy.deepcopy(baseline)
    elif fault == "legacy":
        from dataclasses import replace

        candidate = replace(candidate, schema_version=1, effective_controls=None)
    elif fault == "samples":
        policy["metrics"]["ttft"]["minimum_samples"] = 21
    elif fault == "stale":
        candidate.slots[1].observations[0]["captured_at"] = "2099-01-01T00:00:00+00:00"
    else:
        candidate.slots[1].observations[0]["quant"] = "Q8_0"
    if fault in ("stale", "configuration"):
        data = saved.to_dict()
        row = data["result"]["candidates"][indices["vllm"]]
        slot = candidate.slots[1]
        slot.binding = assemble_binding(
            data,
            row,
            indices["vllm"],
            MonitorRequest("vllm", slot.url, row["model"], ttft_slo=500),
            candidate.target_sources,
            slot.observations,
            retain_prefix=True,
        )
    assert type(candidate) is FleetMonitorReport
    result = api.gate_fleet_monitors(
        baseline, candidate, baseline_plan=saved, candidate_plan=saved, policy=policy
    )
    data = result.to_dict()
    assert result.exit_code == 3 and data["blockers"]
    assert len(data["inputs"]["baseline"]["slots"]) == 3
    assert len(data["inputs"]["candidate"]["slots"]) == 3
    assert len(data["cases"]) == 24


def test_all_output_inputs_are_protected_before_either_write(monitor_source, tmp_path):
    baseline = assembled_report(monitor_source, version_chars=32)
    candidate = assembled_report(monitor_source, version_chars=32, seconds=2)
    saved, _ = monitor_source
    source = tmp_path / "plan.json"
    saved.save(source)
    result = api.gate_fleet_monitors(
        baseline,
        candidate,
        baseline_plan=source,
        candidate_plan=source,
        policy=policy_for(baseline, candidate),
    )
    original = source.read_bytes()
    out = tmp_path / "decision.json"
    with pytest.raises(api.PlanError):
        api.write_fleet_monitor_gate(result, out=out, junit=source)
    assert source.read_bytes() == original and not out.exists()


def test_native_candidate_breach_is_failure_but_partial_eligibility_wins(monitor_source, tmp_path):
    from chimeraforge.monitor import MonitorRequest
    from chimeraforge.monitor_binding import assemble_binding

    baseline = assembled_report(monitor_source, version_chars=32)
    candidate = assembled_report(monitor_source, version_chars=32, seconds=2, ttft=0.7)
    saved, indices = monitor_source
    policy = policy_for(baseline, candidate)
    result = api.gate_fleet_monitors(
        baseline, candidate, baseline_plan=saved, candidate_plan=saved, policy=policy
    )
    assert candidate.exit_code == 3 and result.exit_code == 1
    path = tmp_path / "breach.xml"
    api.write_fleet_monitor_gate(result, junit=path)
    assert ET.fromstring(path.read_bytes()).attrib["failures"] == "12"
    slot = candidate.slots[-1]
    slot.state = "cancelled"
    slot.windows = slot.windows[:1]
    slot.observations = slot.observations[:1]
    data = saved.to_dict()
    row = data["result"]["candidates"][indices["vllm"]]
    slot.binding = assemble_binding(
        data,
        row,
        indices["vllm"],
        MonitorRequest("vllm", slot.url, row["model"], ttft_slo=500),
        candidate.target_sources,
        slot.observations,
        retain_prefix=True,
    )
    candidate.budget["termination"] = "observation_deadline"
    partial = api.gate_fleet_monitors(
        baseline, candidate, baseline_plan=saved, candidate_plan=saved, policy=policy
    )
    assert candidate.exit_code == 3 and partial.exit_code == 3
    assert len(partial.to_dict()["cases"]) == 24
    assert any(case["native_outcome"] == "breach" for case in partial.to_dict()["cases"])
    api.write_fleet_monitor_gate(partial, junit=path)
    assert ET.fromstring(path.read_bytes()).attrib["errors"] == "25"


@pytest.mark.parametrize(
    "path,value",
    [
        (("schema_version",), True),
        (("original_replicas",), 17),
        (("windows",), 257),
        (("endpoint_ids",), ["r0", "r0", "r2"]),
        (("metrics",), {"itl": {"minimum_samples": 20}}),
        (("metrics", "ttft", "minimum_samples"), True),
        (("metrics", "ttft", "minimum_samples"), 0),
        (("baseline", "plan", "candidate_index"), True),
        (("candidate", "plan", "fingerprint"), "not-a-fingerprint"),
        (("candidate", "controls", "targets", "tpot_ms"), 25),
    ],
)
def test_policy_must_explicitly_admit_closed_source_population_and_native_metrics(
    monitor_source, path, value
):
    baseline = assembled_report(monitor_source, version_chars=32)
    candidate = assembled_report(monitor_source, version_chars=32, seconds=2)
    saved, _ = monitor_source
    policy = policy_for(baseline, candidate)
    target = policy
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(api.PlanError):
        api.gate_fleet_monitors(
            baseline, candidate, baseline_plan=saved, candidate_plan=saved, policy=policy
        )


def test_equivalent_real_and_endpoint_label_copy_is_ineligible(monitor_source):
    from chimeraforge.monitor import MonitorRequest
    from chimeraforge.monitor_binding import assemble_binding

    baseline = assembled_report(monitor_source, version_chars=32)
    candidate = copy.deepcopy(baseline)
    candidate.cleanup["budget_seconds"] = 2.0
    candidate.effective_controls["cleanup_seconds"] = 2.0
    saved, indices = monitor_source
    data = saved.to_dict()
    row = data["result"]["candidates"][indices["vllm"]]
    for i, slot in enumerate(candidate.slots):
        slot.url = f"http://other-label.invalid/r{i}/metrics"
        candidate.effective_controls["endpoints"][i]["url"] = slot.url
        slot.binding = assemble_binding(
            data,
            row,
            indices["vllm"],
            MonitorRequest("vllm", slot.url, row["model"], ttft_slo=500),
            candidate.target_sources,
            slot.observations,
            retain_prefix=True,
        )
    result = api.gate_fleet_monitors(
        baseline,
        candidate,
        baseline_plan=saved,
        candidate_plan=saved,
        policy=policy_for(baseline, candidate),
    )
    assert result.exit_code == 3
    assert result.to_dict()["blockers"] == ["equivalent_observed_window_payload"]


def test_sglang_known_itl_cannot_replace_requested_tpot(monitor_source):
    baseline = assembled_report(monitor_source, version_chars=32, backend="sglang", tpot_slo=25)
    candidate = assembled_report(
        monitor_source, version_chars=32, seconds=2, backend="sglang", tpot_slo=25
    )
    metric = candidate.slots[0].windows[0].metrics
    assert metric["itl"].samples == 20 and metric["tpot"].samples is None
    assert candidate.exit_code == 4
    saved, _ = monitor_source
    policy = policy_for(baseline, candidate)
    policy["metrics"]["tpot"] = {"minimum_samples": 20}
    result = api.gate_fleet_monitors(
        baseline, candidate, baseline_plan=saved, candidate_plan=saved, policy=policy
    )
    assert result.exit_code == 3
    assert len(result.to_dict()["cases"]) == 48
    assert all(
        row["native_outcome"] == "unknown"
        for row in result.to_dict()["cases"]
        if row["metric"] == "tpot"
    )


@pytest.mark.parametrize("reverse", [False, True])
def test_both_unequal_native_populations_keep_every_actual_member(
    monitor_source, monitor_source_one, reverse, tmp_path
):
    sources = [monitor_source, monitor_source_one]
    if reverse:
        sources.reverse()
    baseline = assembled_report(sources[0], version_chars=32)
    candidate = assembled_report(sources[1], version_chars=32, seconds=2, ttft=0.7)
    policy = policy_for(baseline, candidate)
    urls = {slot.id: slot.url for slot in candidate.slots}
    policy["candidate"]["controls"]["endpoints"] = [
        {"id": name, "url": urls.get(name, f"http://declared-policy.invalid/{name}/metrics")}
        for name in policy["endpoint_ids"]
    ]
    result = api.gate_fleet_monitors(
        baseline,
        candidate,
        baseline_plan=sources[0][0],
        candidate_plan=sources[1][0],
        policy=policy,
    )
    data = result.to_dict()
    assert result.exit_code == 3 and candidate.exit_code == 3
    assert "candidate:original_population_mismatch" in data["blockers"]
    assert len(data["inputs"]["baseline"]["slots"]) == len(baseline.slots)
    assert len(data["inputs"]["candidate"]["slots"]) == len(candidate.slots)
    assert all(
        len(slot["windows"]) == 4
        for arm in ("baseline", "candidate")
        for slot in data["inputs"][arm]["slots"]
    )
    assert any(case["native_outcome"] == "breach" for case in data["cases"])
    junit = tmp_path / "unequal.xml"
    api.write_fleet_monitor_gate(result, junit=junit)
    suite = ET.fromstring(junit.read_bytes())
    assert suite.attrib["tests"] == suite.attrib["errors"] == str(1 + len(data["cases"]))


@pytest.mark.parametrize("legacy", [False, True])
def test_declared_cell_union_never_multiplies_unmatched_members_by_policy_windows(
    monitor_source_sixteen, legacy, tmp_path
):
    from dataclasses import replace

    baseline = assembled_report(
        monitor_source_sixteen, version_chars=32, window_count=1, tpot_slo=25
    )
    candidate = assembled_report(
        monitor_source_sixteen, version_chars=32, window_count=1, seconds=2, tpot_slo=25
    )
    saved, _ = monitor_source_sixteen
    policy = policy_for(baseline, candidate)
    policy.update(original_replicas=1, endpoint_ids=["declared"], windows=256)
    policy["metrics"]["tpot"] = {"minimum_samples": 20}
    for arm in ("baseline", "candidate"):
        policy[arm]["controls"].update(
            endpoints=[{"id": "declared", "url": "http://policy.invalid/metrics"}],
            windows=256,
            observation_seconds=600,
            max_requests=2048,
        )
    if legacy:
        baseline = replace(baseline, schema_version=1, effective_controls=None)
        candidate = replace(candidate, schema_version=1, effective_controls=None)
    result = api.gate_fleet_monitors(
        baseline, candidate, baseline_plan=saved, candidate_plan=saved, policy=policy
    )
    assert result.exit_code == 3
    print("actual constructed metric cells", len(result._data["cases"]))
    data = result.to_dict()
    assert len(data["cases"]) == 1088
    assert all(len(data["inputs"][arm]["slots"]) == 16 for arm in ("baseline", "candidate"))
    assert all(
        case["window_index"] == 0 for case in data["cases"] if case["member_id"] != "declared"
    )
    junit = tmp_path / "domain.xml"
    api.write_fleet_monitor_gate(result, junit=junit)
    suite = ET.fromstring(junit.read_bytes())
    assert suite.attrib["tests"] == suite.attrib["errors"] == "1089"


@pytest.mark.parametrize("legacy", [False, True])
def test_common_member_retains_actual_extra_declared_or_observed_windows(monitor_source, legacy):
    from dataclasses import replace

    baseline = assembled_report(monitor_source, version_chars=32)
    candidate = assembled_report(monitor_source, version_chars=32, seconds=2)
    saved, _ = monitor_source
    policy = policy_for(baseline, candidate)
    policy["windows"] = 1
    for arm in ("baseline", "candidate"):
        policy[arm]["controls"]["windows"] = 1
    if legacy:
        baseline = replace(baseline, schema_version=1, effective_controls=None)
        candidate = replace(candidate, schema_version=1, effective_controls=None)
    result = api.gate_fleet_monitors(
        baseline, candidate, baseline_plan=saved, candidate_plan=saved, policy=policy
    )
    assert result.exit_code == 3
    assert len(result.to_dict()["cases"]) == 24
