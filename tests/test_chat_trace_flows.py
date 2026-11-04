"""Chat bindings through existing saved/fleet/campaign native receivers and gates."""

from dataclasses import asdict, replace
from collections import Counter
import json

import pytest

from chimeraforge import api
from chimeraforge.bench import trace
from chimeraforge.bench.trace_campaign_inputs import load_campaign
from chimeraforge.bench.trace_gate_inputs import load_trace
from test_chat_trace import chat_row
from test_plan_trace import ObservedBackend, saved as saved
from test_fleet_trace import Node, Scene, endpoints, routes
from test_fleet_monitor import native_fleet as native_fleet


class ChatObservedBackend(ObservedBackend):
    async def chat_observed(self, model, messages, options, on_first_output):
        # The existing controlled metadata fixture stores the intact list, not flattened text.
        return await super().generate_observed(model, messages, options, on_first_output)


class ChatNode(Node):
    async def chat_observed(self, model, messages, options, on_first_output):
        return await super().generate_observed(model, messages, options, on_first_output)


def conversations(count, cap):
    rows = []
    for index in range(count):
        row = chat_row(
            str(index),
            max_output_tokens=cap,
            arrival_offset_s=index * 0.001,
            temperature=float(index % 3) / 4,
        )
        if index % 2:
            row = replace(
                row,
                messages=(
                    *row.messages,
                    api.ChatMessage("assistant", f"private prior answer {index}"),
                    api.ChatMessage("user", f"private followup {index}"),
                ),
            )
        rows.append(row)
    return rows


def message_key(messages):
    return json.dumps(messages, sort_keys=True)


def assert_calls(calls, expected_rows):
    expected = {message_key([asdict(m) for m in r.messages]): r for r in expected_rows}
    assert Counter(message_key(c[1]) for c in calls) == Counter(expected.keys())
    assert all(c[2]["temperature"] == expected[message_key(c[1])].temperature for c in calls)


@pytest.mark.asyncio
async def test_chat_saved_plan_native_counts_and_serial_campaign_receiving(saved, monkeypatch):
    created = []

    def factory(name, **kwargs):
        backend = ChatObservedBackend(saved)
        created.append(backend)
        return backend

    monkeypatch.setattr(trace, "get_backend", factory)
    requests = conversations(2, 4)
    original = saved.to_dict()
    receipt = await api.replay_plan_trace(saved, requests, request_timeout=2, trace_timeout=5)
    data = receipt.to_dict()
    assert data["native_trace"]["execution"]["completed"] == 2
    assert load_trace(data["native_trace"])["data"] == data["native_trace"]
    assert data["ordered_descriptors"] == [
        row["descriptor"] for row in data["native_trace"]["requests"]
    ]
    assert all(row["mode"] == "chat" for row in data["ordered_descriptors"])
    assert data["binding"]["token_lengths"]["prompt_tokens"]["expected"] == 8
    assert data["binding"]["token_lengths"]["prompt_tokens"]["state"] == "matched"
    selected = saved.candidate(0)
    backend = {"llama.cpp": "ollama"}.get(selected.backend, selected.backend)
    campaign = await api.replay_trace_campaign(
        requests,
        model=selected.model.removeprefix("ollama:"),
        backend=backend,
        replicates=2,
        concurrency=2,
        request_timeout=2,
        trace_timeout=5,
        campaign_timeout=15,
    )
    assert load_campaign(campaign)["data"] == campaign.to_dict()
    assert all(
        row["mode"] == "chat" for row in campaign.to_dict()["manifest"]["ordered_descriptors"]
    )
    assert all(node.closed for node in created) and saved.to_dict() == original
    for node in created:
        assert_calls(node.calls, requests)


@pytest.mark.asyncio
async def test_chat_whole_fleet_campaign_receiving_and_original_routes(
    native_fleet, monkeypatch, tmp_path
):
    saved, indices = native_fleet
    scene = Scene(saved, indices["vllm"])

    def factory(name, *, base_url, **kwargs):
        node = ChatNode(scene, name, base_url)
        scene.created.append(node)
        return node

    monkeypatch.setattr(trace, "get_backend", factory)
    cap = saved.candidate(indices["vllm"]).decode_tokens_per_req
    requests = conversations(6, cap)
    before = saved.to_dict()
    receipt = await api.replay_fleet_trace(
        saved,
        requests,
        endpoints(),
        routes(requests),
        candidate_index=indices["vllm"],
        concurrency=2,
        request_timeout=2,
        trace_timeout=5,
    )
    data = receipt.to_dict()
    assert data["native_trace"]["execution"]["completed"] == 6
    assert len(data["slots"]) == 3 and scene.peak <= 2
    assert api.load_fleet_trace(data).to_dict() == data
    path = tmp_path / "chat-fleet.json"
    receipt.save(path)
    assert api.load_fleet_trace(path).to_dict() == data
    campaign = await api.replay_fleet_trace_campaign(
        saved,
        requests,
        endpoints(),
        routes(requests),
        executions=2,
        candidate_index=indices["vllm"],
        concurrency=2,
        request_timeout=2,
        trace_timeout=5,
        campaign_timeout=15,
    )
    assert api.load_fleet_trace_campaign(campaign).to_dict() == campaign.to_dict()
    assert saved.to_dict() == before and all(node.closed for node in scene.created)
    expected_routes = {
        endpoint.url: [row for i, row in enumerate(requests) if i % 3 == index]
        for index, endpoint in enumerate(endpoints())
    }
    for node in scene.created:
        assert_calls(node.calls, expected_routes[node.url])
    assert "private exact" not in json.dumps(data)


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["role_order", "temperature", "mode"])
async def test_chat_one_row_changes_gate_identity_even_with_same_visible_counts(
    saved, monkeypatch, change
):
    monkeypatch.setattr(trace, "get_backend", lambda *a, **k: ChatObservedBackend(saved))
    selected = saved.candidate(0)
    backend = {"llama.cpp": "ollama"}.get(selected.backend, selected.backend)
    rows = conversations(2, 4)
    altered = list(rows)
    if change == "role_order":
        altered[1] = replace(rows[1], messages=tuple(reversed(rows[1].messages)))
    elif change == "temperature":
        altered[1] = replace(rows[1], temperature=0.75)
    else:
        # An independent legacy prompt request, never a flattened chat fallback.
        altered[1] = api.TraceRequest(
            rows[1].request_id, "independent plain prompt", 4, rows[1].arrival_offset_s
        )
    left = await api.replay_trace(
        rows, model=selected.model.removeprefix("ollama:"), backend=backend
    )
    right = await api.replay_trace(
        altered, model=selected.model.removeprefix("ollama:"), backend=backend
    )
    assert left.to_dict()["workload"] != right.to_dict()["workload"]
    result = api.gate_traces(
        [left], [right], policy=api.TraceGatePolicy(require_cache_evidence=False)
    ).to_dict()
    assert result["exit_code"] == 3
    assert "workload_or_actual_lengths_changed" in result["blockers"]
