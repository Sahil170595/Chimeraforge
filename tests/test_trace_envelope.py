"""Finite load-cell oracles over whole synthetic campaigns, without inference claims."""

from __future__ import annotations

import copy
from dataclasses import asdict
import hashlib
import json
import math
import os
from types import SimpleNamespace

import pytest

from chimeraforge import api
from chimeraforge.bench.trace_campaign import TraceCampaign
from chimeraforge.bench.trace_campaign_inputs import load_campaign
from chimeraforge.bench.trace_workload import TraceRequest, descriptor
from chimeraforge.planner.replay import digest
from test_trace_campaign_gate import campaign, incomplete, reseal
from test_trace_gate import finish


def pack(value):
    cursor = 0.0
    for slot in value["replicas"]:
        native = slot["receipt"]
        native["execution"]["elapsed_seconds"] = (
            max(row["times"]["terminal_s"] for row in native["requests"]) + 0.01
        )
        native["clock"]["origin"] = value["clock"]["origin"] + cursor + 0.1
        native["goodput"]["planned_horizon_seconds"] = max(
            row["descriptor"]["arrival_offset_s"] for row in native["requests"]
        )
        finish(native)
        slot["start_s"] = cursor
        slot["end_s"] = cursor + native["execution"]["elapsed_seconds"] + 0.2
        slot["workload_ref"] = value["manifest"]["workload"]["canonical_sha256"]
        cursor = slot["end_s"] + 0.1
    value["clock"]["elapsed_seconds"] = cursor
    return reseal(value)


def uniform(interval=0.1, *, durations=(0.12, 0.14, 0.16)):
    value = campaign(durations=durations)
    workload = [
        TraceRequest(str(i), "PRIVATE INPUT", 8, float(i) * float(interval)) for i in range(2)
    ]
    manifest = value["manifest"]
    manifest["ordered_descriptors"] = [descriptor(row) for row in workload]
    manifest["workload"] = {
        "canonical_sha256": digest([asdict(row) for row in workload]),
        "raw_sha256": None,
    }
    for slot, duration in zip(value["replicas"], durations):
        native = slot["receipt"]
        native["workload"] = {**manifest["workload"], "raw_sha256": None}
        for row, requested in zip(native["requests"], manifest["ordered_descriptors"]):
            row["descriptor"] = copy.deepcopy(requested)
            offset = requested["arrival_offset_s"]
            row["times"] = {
                "scheduled_s": offset,
                "arrival_s": offset,
                "start_s": offset,
                "first_output_s": offset + 0.02,
                "terminal_s": offset + duration,
            }
    return pack(value)


def declarations():
    source = uniform()
    controls = source["manifest"]["controls"]
    cases = {
        "schema_version": 1,
        "kind": "chimeraforge.trace-envelope-cases",
        **{
            key: controls[key]
            for key in (
                "model",
                "backend",
                "concurrency",
                "request_timeout_seconds",
                "trace_timeout_seconds",
                "campaign_timeout_seconds",
            )
        },
        "expected_replicates": 3,
        "ordered_descriptors": [
            {key: item for key, item in row.items() if key != "arrival_offset_s"}
            for row in source["manifest"]["ordered_descriptors"]
        ],
        "cells": [
            {"name": "slow", "arrival_interval_seconds": 0.1},
            {"name": "fast", "arrival_interval_seconds": 0.05},
        ],
    }
    policy = {
        "schema_version": 1,
        "kind": "chimeraforge.trace-envelope-policy",
        "targets": dict(controls["targets"]),
        "fixed_controls": {},
        "require_cache_evidence": True,
    }
    return cases, policy


def assess(campaigns=None, *, cases=None, policy=None):
    from chimeraforge.bench.trace_envelope import assess_trace_envelope

    declared, chosen = declarations()
    return assess_trace_envelope(
        declared if cases is None else cases,
        {"slow": uniform(), "fast": uniform(0.05)} if campaigns is None else campaigns,
        policy=chosen if policy is None else policy,
    )


def test_distinct_legitimate_schedules_rank_only_highest_observed_passing_cell():
    result = assess().to_dict()
    assert result["exit_code"] == 0 and result["outcome"] == "conditional_pass"
    assert result["highest_observed_passing"] == {
        "cell": "fast",
        "arrival_interval_seconds": 0.05,
        "nominal_rate_rps": 20.0,
    }
    assert [cell["observed_outcome"] for cell in result["cells"]] == ["observed_pass"] * 2
    assert result["assurance"]["independent_executions_verified"] is False
    assert "PRIVATE" not in json.dumps(result)


def test_missing_higher_cell_retains_lower_point_and_named_missing_population():
    result = assess({"slow": uniform()}).to_dict()
    assert result["exit_code"] == 3
    assert result["highest_observed_passing"]["cell"] == "slow"
    missing = result["cells"][1]
    assert missing["name"] == "fast" and missing["execution_state"] == "missing"
    assert len(missing["replicas"]) == 3 and all(
        slot["state"] == "missing" for slot in missing["replicas"]
    )


@pytest.mark.parametrize("unavailable", ["clock", "prompt_tokens", "tokens_generated"])
def test_complete_native_execution_needs_observed_clock_and_positive_actual_lengths(unavailable):
    campaigns = {"slow": uniform(), "fast": uniform(0.05)}
    for campaign_ in campaigns.values():
        for slot in campaign_["replicas"]:
            native = slot["receipt"]
            if unavailable == "clock":
                native["clock"]["origin"] = None
                native["execution"]["elapsed_seconds"] = None
            else:
                for row in native["requests"]:
                    row["native"][unavailable] = 0
                    if unavailable == "tokens_generated":
                        row["native"]["throughput_tps"] = 0.0
                        row["mean_tpot_ms"] = None
                        row["mean_tpot_basis"] = "unavailable"
            finish(native)
        reseal(campaign_)
        assert load_campaign(campaign_)["data"]["exit_code"] == 0
    result = assess(campaigns).to_dict()
    assert result["exit_code"] == 3 and result["highest_observed_passing"] is None
    assert all(cell["observed_outcome"] == "observed_pass" for cell in result["cells"])
    blocker = (
        "clock_origin_unavailable" if unavailable == "clock" else "observed_token_lengths_unavailable"
    )
    assert all(blocker in cell["blockers"] for cell in result["cells"])


def test_missing_native_clock_only_blocks_its_cell_and_retains_known_breaches():
    high = uniform(0.05)
    row = high["replicas"][1]["receipt"]["requests"][0]
    row["times"]["terminal_s"] = row["times"]["scheduled_s"] + 3.0
    pack(high)
    for slot in high["replicas"]:
        native = slot["receipt"]
        native["clock"]["origin"] = None
        native["execution"]["elapsed_seconds"] = None
        finish(native)
    reseal(high)
    assert load_campaign(high)["data"]["exit_code"] == 0
    result = assess({"slow": uniform(), "fast": high}).to_dict()
    assert result["exit_code"] == 3 and result["highest_observed_passing"]["cell"] == "slow"
    assert result["cells"][1]["observed_outcome"] == "breach"
    assert result["known_breaches"][0]["target"] == "latency_ms"


def test_every_request_and_replica_must_pass_not_average_or_survivor_selection():
    high = uniform(0.05)
    row = high["replicas"][2]["receipt"]["requests"][1]
    row["times"]["terminal_s"] = row["times"]["scheduled_s"] + 3.0
    pack(high)
    result = assess({"slow": uniform(), "fast": high}).to_dict()
    assert result["exit_code"] == 1 and result["cells"][1]["observed_outcome"] == "breach"
    assert result["highest_observed_passing"]["cell"] == "slow"
    assert result["known_breaches"] == [
        {
            "cell": "fast",
            "replica_index": 2,
            "request_id": "1",
            "target": "latency_ms",
            "observed": 3000.0,
            "threshold": 2000.0,
        }
    ]


def test_failed_and_unstarted_slots_remain_visible_without_erasing_lower_point():
    high = incomplete(uniform(0.05), index=1, failed=True)
    result = assess({"slow": uniform(), "fast": high}).to_dict()
    assert result["exit_code"] == 3 and result["highest_observed_passing"]["cell"] == "slow"
    assert [slot["state"] for slot in result["cells"][1]["replicas"]] == [
        "completed",
        "failed",
        "not_started",
    ]
    assert result["cells"][1]["observed_outcome"] == "unavailable"


def test_unknown_anchor_cannot_hide_known_control_conflicts_across_other_replicas():
    low, high = uniform(), uniform(0.05)
    for phase in ("serving_before", "serving_after"):
        low["replicas"][0]["receipt"][phase]["context_length"] = None
        high["replicas"][1]["receipt"][phase]["context_length"] = 4096
    pack(low), pack(high)
    result = assess({"slow": low, "fast": high}).to_dict()
    assert result["exit_code"] == 3 and result["highest_observed_passing"] is None
    assert result["compatibility"]["conditions"]["context_length"]["state"] == "mismatch"
    assert all(cell["observed_outcome"] == "observed_pass" for cell in result["cells"])


@pytest.mark.parametrize("field", ["prompt_tokens", "tokens_generated", "cached_prompt_tokens"])
def test_all_known_actual_lengths_and_cache_values_are_compared(field):
    low, high = uniform(), uniform(0.05)
    low["replicas"][0]["receipt"]["requests"][0]["native"][field] = None
    native = high["replicas"][1]["receipt"]
    native["requests"][0]["native"][field] = 3
    if field == "tokens_generated":
        low["replicas"][0]["receipt"]["requests"][0]["mean_tpot_ms"] = None
        native["requests"][0]["native"]["throughput_tps"] = 30.0
        native["requests"][0]["mean_tpot_ms"] = 100 / 3
    if field == "cached_prompt_tokens":
        native["serving_before"]["prefix_cache"] = native["serving_after"]["prefix_cache"] = None
    pack(low), pack(high)
    result = assess({"slow": low, "fast": high}).to_dict()
    assert result["exit_code"] == 3 and result["highest_observed_passing"] is None


def test_required_missing_cache_is_explicit_and_unrequired_unknown_controls_do_not_block():
    low = uniform()
    for slot in low["replicas"]:
        native = slot["receipt"]
        for phase in ("serving_before", "serving_after"):
            native[phase]["prefix_cache"] = None
        for row in native["requests"]:
            row["native"]["cached_prompt_tokens"] = None
    pack(low)
    result = assess({"slow": low, "fast": uniform(0.05)}).to_dict()
    assert result["exit_code"] == 3
    assert "cache_evidence_unavailable" in result["cells"][0]["blockers"]
    cases, policy = declarations()
    policy["require_cache_evidence"] = False
    assert (
        assess({"slow": low, "fast": uniform(0.05)}, cases=cases, policy=policy).to_dict()[
            "exit_code"
        ]
        == 0
    )


def test_supported_default_tag_equivalence_preserves_original_observations():
    low = uniform()
    for slot in low["replicas"]:
        slot["receipt"]["serving_after"]["model"] = "synthetic:latest"
    pack(low)
    result = assess({"slow": low, "fast": uniform(0.05)}).to_dict()
    assert result["exit_code"] == 0
    assert (
        result["cells"][0]["replicas"][0]["receipt"]["serving_after"]["model"] == "synthetic:latest"
    )


def test_semantic_copy_inside_campaign_blocks_ranking_despite_relabelled_origin_and_stamp():
    low = uniform()
    duplicate = copy.deepcopy(low["replicas"][0]["receipt"])
    duplicate["created_at"] = "relabelled"
    duplicate["clock"]["origin"] = low["clock"]["origin"] + low["replicas"][1]["start_s"] + 0.1
    low["replicas"][1]["receipt"] = duplicate
    reseal(low)
    result = assess({"slow": low, "fast": uniform(0.05)}).to_dict()
    assert result["exit_code"] == 3 and result["highest_observed_passing"] is None
    assert "duplicate_execution_payload" in result["blockers"]


@pytest.mark.parametrize("interval", [0, -1, True, float("nan"), 5e-324, 1e308, 600])
def test_invalid_or_unrepresentable_loads_are_rejected(interval):
    cases, policy = declarations()
    cases["cells"][0]["arrival_interval_seconds"] = interval
    with pytest.raises(api.PlanError):
        assess(cases=cases, policy=policy)


@pytest.mark.parametrize(
    "mutation",
    [
        "extra",
        "one_request",
        "arrival_in_commitment",
        "duplicates",
        "targets",
        "all_null",
        "bool_replicates",
    ],
)
def test_closed_case_policy_contract(mutation):
    cases, policy = declarations()
    if mutation == "extra":
        cases["private-extra"] = True
    elif mutation == "one_request":
        cases["ordered_descriptors"].pop()
    elif mutation == "arrival_in_commitment":
        cases["ordered_descriptors"][0]["arrival_offset_s"] = 0
    elif mutation == "duplicates":
        cases["cells"][1]["arrival_interval_seconds"] = 0.1
    elif mutation == "targets":
        policy["targets"]["unsupported"] = 1
    elif mutation == "all_null":
        policy["targets"] = dict.fromkeys(policy["targets"])
    else:
        cases["expected_replicates"] = True
    with pytest.raises(api.PlanError):
        assess(cases=cases, policy=policy)


@pytest.mark.parametrize(
    "mutation", ["wrong_cell", "targets", "timeout", "descriptor", "unknown_key", "unreadable"]
)
def test_supplied_cell_mismatch_or_corrupt_source_is_invalid(mutation, tmp_path):
    low, high = uniform(), uniform(0.05)
    mapping = {"slow": low, "fast": high}
    if mutation == "unknown_key":
        mapping["private-unknown"] = low
    elif mutation == "unreadable":
        mapping["fast"] = tmp_path / "missing.json"
    elif mutation == "wrong_cell":
        mapping["fast"] = low
    else:
        key = {"targets": "targets", "timeout": "request_timeout_seconds"}.get(mutation)
        if key is not None:
            high["manifest"]["controls"][key] = (
                1
                if key != "targets"
                else {"latency_ms": 1, "first_output_ms": None, "tpot_ms": None}
            )
        else:
            high["manifest"]["ordered_descriptors"][0]["prompt_sha256"] = "c" * 64
        reseal(high)
    with pytest.raises(api.PlanError):
        assess(mapping)


def test_original_bytes_held_once_and_all_consumed_paths_are_protected(tmp_path, monkeypatch):
    from chimeraforge.bench import trace_envelope_inputs as inputs

    cases, policy = declarations()
    paths = {name: tmp_path / f"{name}.json" for name in ("cases", "policy", "slow", "fast")}
    values = {"cases": cases, "policy": policy, "slow": uniform(), "fast": uniform(0.05)}
    originals = {}
    for name, path in paths.items():
        raw = (json.dumps(values[name], indent=3) + "\n\n").encode()
        path.write_bytes(raw)
        originals[name] = raw
    result = assess(
        {"slow": paths["slow"], "fast": paths["fast"]}, cases=paths["cases"], policy=paths["policy"]
    )
    report = result.to_dict()
    for role in ("cases", "policy"):
        assert report["inputs"][role]["sha256"] == hashlib.sha256(originals[role]).hexdigest()
    assert report["budgets"]["campaigns"]["charged_bytes"] == sum(
        len(originals[k]) for k in ("slow", "fast")
    )
    for source in paths.values():
        with pytest.raises(api.PlanError):
            result.save(source)
    alias = tmp_path / "alias.json"
    os.link(paths["slow"], alias)
    with pytest.raises(api.PlanError):
        result.save(alias)
    private = tmp_path / "private-workload.json"
    typed = TraceCampaign(uniform(), (private,))
    result = assess({"slow": typed, "fast": uniform(0.05)})
    with pytest.raises(api.PlanError):
        result.save(private)
    copy_out = result.to_dict()
    copy_out["cells"].clear()
    assert len(result.to_dict()["cells"]) == 2
    assert inputs.MAX_CASES_BYTES == 1024 * 1024


def test_schedule_roundoff_within_four_ulps_is_preserved_and_larger_drift_refused():
    value = uniform()
    shifted = math.nextafter(0.1, math.inf)
    value["manifest"]["ordered_descriptors"][1]["arrival_offset_s"] = shifted
    for slot in value["replicas"]:
        row = slot["receipt"]["requests"][1]
        row["descriptor"]["arrival_offset_s"] = shifted
        row["times"]["scheduled_s"] = shifted
        row["times"]["arrival_s"] = shifted
        row["times"]["start_s"] = shifted
    pack(value)
    result = assess({"slow": value, "fast": uniform(0.05)}).to_dict()
    assert (
        result["cells"][0]["replicas"][0]["receipt"]["requests"][1]["descriptor"][
            "arrival_offset_s"
        ]
        == shifted
    )
    for _ in range(6):
        shifted = math.nextafter(shifted, math.inf)
    value["manifest"]["ordered_descriptors"][1]["arrival_offset_s"] = shifted
    for slot in value["replicas"]:
        row = slot["receipt"]["requests"][1]
        row["descriptor"]["arrival_offset_s"] = shifted
        for key in ("scheduled_s", "arrival_s", "start_s"):
            row["times"][key] = shifted
    pack(value)
    with pytest.raises(api.PlanError):
        assess({"slow": value, "fast": uniform(0.05)})


def test_active_mean_timing_target_cannot_rank_different_known_native_bases():
    cases, policy = declarations()
    cases["backend"] = "vllm"
    policy["targets"]["tpot_ms"] = 500
    values = {"slow": uniform(), "fast": uniform(0.05)}
    for name, value in values.items():
        controls = value["manifest"]["controls"]
        controls["backend"] = "vllm"
        controls["targets"] = dict(policy["targets"])
        for slot in value["replicas"]:
            native = slot["receipt"]
            native["backend"] = "vllm"
            native["targets"] = dict(policy["targets"])
            for phase in ("serving_before", "serving_after"):
                native[phase]["backend"] = "vllm"
            for request in native["requests"]:
                basis = "content" if name == "slow" else "native-output"
                request["mean_tpot_basis"] = f"client-first-to-last-{basis}/(server-output-count-1)"
                request["mean_tpot_ms"] = 100 / 3
                request["native"].update(
                    ttft_basis="client-stream-first-content", throughput_tps=30.0
                )
        pack(value)
        load_campaign(value)
    result = assess(values, cases=cases, policy=policy).to_dict()
    assert result["exit_code"] == 3 and result["highest_observed_passing"] is None
    assert "mean_timing_basis_changed" in result["blockers"]
    assert all(cell["observed_outcome"] == "observed_pass" for cell in result["cells"])
    assert result["cells"][0]["replicas"][0]["receipt"]["requests"][0]["mean_tpot_basis"] == (
        "client-first-to-last-content/(server-output-count-1)"
    )


def repeated_source(tmp_path):
    cases, policy = declarations()
    cases["cells"][1]["arrival_interval_seconds"] = math.nextafter(0.1, math.inf)
    path = tmp_path / "shared.json"
    raw = json.dumps(uniform()).encode()
    path.write_bytes(raw)
    return cases, policy, path, raw


def test_repeated_path_held_once_but_each_declared_occurrence_is_charged(tmp_path, monkeypatch):
    from chimeraforge.bench import trace_envelope_inputs as inputs

    cases, policy, path, raw = repeated_source(tmp_path)
    loader = inputs.load_campaign
    calls = []

    def counted(source, *, limit):
        calls.append(source)
        return loader(source, limit=limit)

    monkeypatch.setattr(inputs, "load_campaign", counted)
    result = assess({"slow": path, "fast": path}, cases=cases, policy=policy).to_dict()
    assert calls == [path]
    assert result["budgets"]["campaigns"]["charged_bytes"] == 2 * len(raw)
    assert result["highest_observed_passing"] is None
    assert "duplicate_execution_payload" in result["blockers"]


def test_repeated_occurrence_budget_is_checked_before_cached_snapshot_clone(tmp_path, monkeypatch):
    from chimeraforge.bench import trace_envelope_inputs as inputs

    cases, policy, path, raw = repeated_source(tmp_path)
    clones = []
    monkeypatch.setattr(inputs, "MAX_CAMPAIGN_TOTAL_BYTES", 2 * len(raw) - 1)
    monkeypatch.setattr(
        inputs, "copy", SimpleNamespace(deepcopy=lambda value: clones.append(value))
    )
    with pytest.raises(api.PlanError, match="budget"):
        assess({"slow": path, "fast": path}, cases=cases, policy=policy)
    assert clones == []


@pytest.mark.parametrize("role", ["cases", "policy"])
def test_separate_declaration_budgets_refuse_oversize_before_campaign_load(role, monkeypatch):
    from chimeraforge.bench import trace_envelope_inputs as inputs

    called = []
    monkeypatch.setattr(inputs, "MAX_CASES_BYTES" if role == "cases" else "MAX_POLICY_BYTES", 16)
    monkeypatch.setattr(inputs, "load_campaign", lambda *args, **kwargs: called.append(args))
    with pytest.raises(api.PlanError, match="bounded declaration"):
        assess()
    assert called == []


def test_typed_private_label_can_also_be_later_campaign_source(tmp_path):
    high_path = tmp_path / "higher.json"
    high_path.write_text(json.dumps(uniform(0.05)))
    low = TraceCampaign(uniform(), (high_path,))
    result = assess({"slow": low, "fast": high_path})
    assert result.to_dict()["exit_code"] == 0
    with pytest.raises(api.PlanError):
        result.save(high_path)


def test_all_failed_population_is_retained_and_required_unknown_control_blocks_local_point():
    cases, policy = declarations()
    failed = incomplete(uniform(0.05), index=0, failed=True)
    low = uniform()
    for slot in low["replicas"]:
        for phase in ("serving_before", "serving_after"):
            slot["receipt"][phase]["context_length"] = None
    pack(low)
    policy["fixed_controls"] = {"context_length": 2048}
    result = assess({"slow": low, "fast": failed}, cases=cases, policy=policy).to_dict()
    assert result["exit_code"] == 3 and result["highest_observed_passing"] is None
    assert [slot["state"] for slot in result["cells"][1]["replicas"]] == [
        "failed",
        "not_started",
        "not_started",
    ]
    assert result["cells"][0]["observed_outcome"] == "observed_pass"
    assert result["compatibility"]["conditions"]["context_length"]["state"] == "unavailable"
