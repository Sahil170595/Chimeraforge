"""Whole-fleet admission and privacy fail before any backend construction."""

from __future__ import annotations

import asyncio
from dataclasses import replace
import json

import pytest

from chimeraforge import api
from test_fleet_trace import endpoints, routes, scene as scene, workload
from test_fleet_monitor import native_fleet as native_fleet


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "fault",
    [
        "missing_member",
        "duplicate_id",
        "alias_url",
        "port_zero",
        "userinfo",
        "query",
        "fragment",
        "missing_route",
        "duplicate_route",
        "unknown_member",
        "request_cap",
        "huge_timeout",
    ],
)
async def test_invalid_whole_selection_does_not_construct_any_backend(native_fleet, scene, fault):
    saved, indices = native_fleet
    requests = workload(saved, indices["vllm"])
    members, mapping, options = endpoints(), routes(requests), {}
    if fault == "missing_member":
        members = members[:-1]
    elif fault == "duplicate_id":
        members = (*members[:-1], replace(members[2], id=members[0].id))
    elif fault == "alias_url":
        members = (*members[:-1], replace(members[2], url=members[0].url + "/./"))
    elif fault == "port_zero":
        members = (*members[:-1], replace(members[2], url="http://member-2.invalid:0"))
    elif fault in ("userinfo", "query", "fragment"):
        values = {
            "userinfo": "http://PRIVATE:SECRET@host.invalid",
            "query": "http://host.invalid?x=1",
            "fragment": "http://host.invalid#private",
        }
        members = (*members[:-1], replace(members[2], url=values[fault]))
    elif fault == "missing_route":
        mapping = mapping[:-1]
    elif fault == "duplicate_route":
        mapping[-1] = mapping[0]
    elif fault == "unknown_member":
        mapping[-1] = replace(mapping[-1], endpoint_id="foreign")
    elif fault == "request_cap":
        requests[-1] = replace(requests[-1], max_output_tokens=requests[-1].max_output_tokens - 1)
    else:
        options["request_timeout"] = 10**1000
    with pytest.raises(api.PlanError):
        await api.replay_fleet_trace(
            saved, requests, members, mapping, candidate_index=indices["vllm"], **options
        )
    assert not scene.created


@pytest.mark.asyncio
async def test_explicit_empty_connection_mapping_requires_https_for_all_before_contact(
    native_fleet, scene
):
    saved, indices = native_fleet
    requests = workload(saved, indices["vllm"])
    with pytest.raises(api.MonitorConnectionError):
        await api.replay_fleet_trace(
            saved,
            requests,
            endpoints(),
            routes(requests),
            candidate_index=indices["vllm"],
            connections={},
        )
    assert not scene.created


@pytest.mark.asyncio
async def test_duplicate_route_json_keys_refused_without_contact(native_fleet, scene, tmp_path):
    saved, indices = native_fleet
    source = tmp_path / "routes.json"
    source.write_text(
        '[{"request_id":"r0","request_id":"r1","endpoint_id":"member-0"}]', encoding="utf-8"
    )
    with pytest.raises(api.PlanError):
        await api.replay_fleet_trace(
            saved,
            workload(saved, indices["vllm"]),
            endpoints(),
            source,
            candidate_index=indices["vllm"],
        )
    assert not scene.created


@pytest.mark.asyncio
async def test_preexisting_stop_retains_original_unstarted_population(native_fleet, scene):
    saved, indices = native_fleet
    requests = workload(saved, indices["vllm"])
    stopped = asyncio.Event()
    stopped.set()
    report = (
        await api.replay_fleet_trace(
            saved,
            requests,
            endpoints(),
            routes(requests),
            candidate_index=indices["vllm"],
            stop_event=stopped,
        )
    ).to_dict()
    assert report["native_trace"]["execution"]["not_started"] == len(requests)
    assert report["native_trace"]["stop_reason"] == "cancelled" and report["exit_code"] == 1
    assert all(node.closed for node in scene.created)
    assert api.load_fleet_trace(report).to_dict() == report


@pytest.mark.asyncio
async def test_route_input_order_is_canonical_but_raw_identity_is_retained(
    native_fleet, scene, tmp_path
):
    from dataclasses import asdict
    import hashlib

    saved, indices = native_fleet
    requests = workload(saved, indices["vllm"])
    source = tmp_path / "routes.json"
    raw = json.dumps([asdict(row) for row in reversed(routes(requests))]).encode()
    source.write_bytes(raw)
    report = (
        await api.replay_fleet_trace(
            saved, requests, endpoints(), source, candidate_index=indices["vllm"]
        )
    ).to_dict()
    assert report["routes"]["rows"] == [asdict(row) for row in routes(requests)]
    assert report["routes"]["raw_sha256"] == hashlib.sha256(raw).hexdigest()
    assert source.read_bytes() == raw and api.load_fleet_trace(report).to_dict() == report
