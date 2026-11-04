"""Native chat receiving, copy detection and declared-load identity."""

import copy

import pytest

from chimeraforge import api
from chimeraforge.bench import trace, trace_gate
from chimeraforge.bench.trace_gate_inputs import load_trace
from chimeraforge.bench.trace_campaign_inputs import load_campaign
from chimeraforge.planner.replay import digest
from test_chat_trace_flows import ChatObservedBackend, conversations
from test_plan_trace import saved as saved
from test_trace_gate import seal


@pytest.mark.asyncio
async def test_chat_semantic_copy_real_temperature_spelling_is_not_new_evidence(saved, monkeypatch):
    monkeypatch.setattr(trace, "get_backend", lambda *a, **k: ChatObservedBackend(saved))
    candidate = saved.candidate(0)
    receipt = await api.replay_trace(
        conversations(2, 4),
        model=candidate.model.removeprefix("ollama:"),
        backend={"llama.cpp": "ollama"}.get(candidate.backend, candidate.backend),
    )
    actual = receipt.to_dict()
    copied = copy.deepcopy(actual)
    assert type(copied["requests"][0]["descriptor"]["temperature"]) is float
    copied["requests"][0]["descriptor"]["temperature"] = 0
    seal(copied)
    # A fingerprint-valid copied claim, not a new authenticated provider execution.
    assert load_trace(copied)["data"] == copied
    assert trace_gate._evidence(load_trace(actual)) == trace_gate._evidence(load_trace(copied))
    changed = copy.deepcopy(copied)
    changed["requests"][1]["descriptor"]["temperature"] = 0.75
    seal(changed)
    assert trace_gate._evidence(load_trace(actual)) != trace_gate._evidence(load_trace(changed))


def mutate_descriptor(descriptor, change):
    if change == "role_order":
        descriptor["messages"].reverse()
        descriptor["message_commitment_sha256"] = digest(descriptor["messages"])
    elif change == "temperature":
        descriptor["temperature"] = 0.75
    else:
        held = {
            key: descriptor[key]
            for key in ("request_id", "max_output_tokens", "arrival_offset_s")
            if key in descriptor
        }
        descriptor.clear()
        descriptor.update(held, prompt_sha256="f" * 64, prompt_bytes=1)


async def campaign_for(saved, monkeypatch):
    monkeypatch.setattr(trace, "get_backend", lambda *a, **k: ChatObservedBackend(saved))
    candidate = saved.candidate(0)
    return await api.replay_trace_campaign(
        conversations(2, 4),
        model=candidate.model.removeprefix("ollama:"),
        backend={"llama.cpp": "ollama"}.get(candidate.backend, candidate.backend),
        replicates=2,
        slos=api.TraceSLO(first_output_ms=1000),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["role_order", "temperature", "mode"])
async def test_chat_campaign_refuses_one_fingerprint_valid_slot_commitment_change(
    saved, monkeypatch, change
):
    campaign = (await campaign_for(saved, monkeypatch)).to_dict()
    assert load_campaign(campaign)["data"] == campaign
    changed = copy.deepcopy(campaign)
    native = changed["replicas"][1]["receipt"]
    mutate_descriptor(native["requests"][1]["descriptor"], change)
    seal(native)
    assert load_trace(native)["data"] == native
    seal(changed)
    with pytest.raises(api.PlanError):
        load_campaign(changed)


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["role_order", "temperature", "mode"])
async def test_chat_envelope_binds_all_declared_fields_to_native_campaign(
    saved, monkeypatch, change
):
    campaign = (await campaign_for(saved, monkeypatch)).to_dict()
    manifest = campaign["manifest"]
    controls = manifest["controls"]
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
        "expected_replicates": 2,
        "ordered_descriptors": [
            {k: copy.deepcopy(v) for k, v in d.items() if k != "arrival_offset_s"}
            for d in manifest["ordered_descriptors"]
        ],
        "cells": [{"name": "chat", "arrival_interval_seconds": 0.001}],
    }
    policy = {
        "schema_version": 1,
        "kind": "chimeraforge.trace-envelope-policy",
        "targets": controls["targets"],
        "fixed_controls": {},
        "require_cache_evidence": False,
    }
    result = api.assess_trace_envelope(cases, {"chat": campaign}, policy=policy).to_dict()
    assert result["cells"][0]["execution_state"] == "completed"
    assert len(result["cells"][0]["replicas"]) == 2
    mutate_descriptor(cases["ordered_descriptors"][1], change)
    with pytest.raises(api.PlanError):
        api.assess_trace_envelope(cases, {"chat": campaign}, policy=policy)
