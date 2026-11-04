"""Chat uses the existing secure client, scheduler and owned-close boundaries."""

import asyncio
import json
import logging

import pytest

from chimeraforge import api
from chimeraforge.bench import trace
from chimeraforge.bench.trace_gate_inputs import load_trace
from test_chat_trace_flows import ChatObservedBackend, conversations
from test_plan_trace import saved as saved
from test_ci_acceptance import load_script
from test_secure_monitor import certs as certs


@pytest.mark.asyncio
@pytest.mark.parametrize("backend", ["vllm", "sglang"])
async def test_chat_actual_tls_mtls_auth_and_sdk_redaction(certs, backend, caplog):
    secure = load_script("ci_secure_active")
    canary = "FictionalPrivateChat89"
    for name in ("httpx", "httpcore"):
        caplog.set_level(logging.DEBUG, logger=name)
    with secure.server(certs, backend=backend, chat=True, token=canary, mtls=True, echo=canary) as (
        url,
        calls,
    ):
        connection = api.MonitorConnection(
            url,
            ca_bundle=certs["ca"],
            bearer_token=canary,
            client_cert=certs["client"],
            client_key=certs["client_key"],
        )
        result = await api.replay_trace(
            conversations(2, 4),
            model=secure.MODEL,
            backend=backend,
            base_url=url,
            connection=connection,
            request_timeout=2,
            trace_timeout=5,
        )
        data = result.to_dict()
        assert data["execution"]["completed"] == 2
        assert load_trace(data)["data"] == data
        assert data["resource_cleanup"]["state"] == "completed"
        assert calls and all(c["authorized"] and c["client_certificate"] for c in calls)
        assert len([c for c in calls if c["route"] == "v1/chat/completions"]) == 2
        assert canary not in json.dumps(data) + caplog.text
        assert "private exact" not in json.dumps(data) + caplog.text
        before = certs["ca"].read_bytes()
        with pytest.raises(api.PlanError):
            result.save(certs["ca"])
        assert certs["ca"].read_bytes() == before


class BlockedChat(ChatObservedBackend):
    def __init__(self, saved):
        super().__init__(saved)
        self.entered = asyncio.Event()

    async def chat_observed(self, model, messages, options, on_first_output):
        self.entered.set()
        await asyncio.Event().wait()


@pytest.mark.asyncio
async def test_chat_deadline_retains_every_slot_and_closes_backend(saved, monkeypatch):
    backend = BlockedChat(saved)
    monkeypatch.setattr(trace, "get_backend", lambda *a, **k: backend)
    candidate = saved.candidate(0)
    receipt = await api.replay_trace(
        conversations(3, 4),
        model=candidate.model.removeprefix("ollama:"),
        backend={"llama.cpp": "ollama"}.get(candidate.backend, candidate.backend),
        concurrency=1,
        request_timeout=1,
        trace_timeout=0.02,
    )
    data = receipt.to_dict()
    assert len(data["requests"]) == 3 and backend.entered.is_set() and backend.closed
    assert data["stop_reason"] == "trace_deadline"
    assert data["resource_cleanup"]["state"] == "completed"
    assert load_trace(data)["data"] == data


@pytest.mark.asyncio
async def test_chat_caller_cancellation_waits_for_owned_backend_close(saved, monkeypatch):
    backend = BlockedChat(saved)
    monkeypatch.setattr(trace, "get_backend", lambda *a, **k: backend)
    candidate = saved.candidate(0)
    task = asyncio.create_task(
        api.replay_trace(
            conversations(3, 4),
            model=candidate.model.removeprefix("ollama:"),
            backend={"llama.cpp": "ollama"}.get(candidate.backend, candidate.backend),
        )
    )
    await asyncio.wait_for(backend.entered.wait(), 2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert backend.closed
