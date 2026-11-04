"""Whole conversation admission precedes backend construction and contact."""

from dataclasses import replace
import json

import pytest

from chimeraforge import api
from chimeraforge.bench import trace
from chimeraforge.bench.backends import BACKEND_REGISTRY, plugin
from chimeraforge.bench.backends.base import Backend
from test_chat_trace import chat_row
from test_chat_trace_flows import ChatObservedBackend
from test_plan_trace import saved as saved


def invalid_row(case):
    row = chat_row("last")
    if case == "bool_temperature":
        return replace(row, temperature=True)
    if case == "nan_temperature":
        return replace(row, temperature=float("nan"))
    if case == "high_temperature":
        return replace(row, temperature=2.1)
    if case == "negative_temperature":
        return replace(row, temperature=-0.1)
    if case == "mutable_messages":
        return replace(row, messages=list(row.messages))
    if case == "empty_messages":
        return replace(row, messages=())
    if case == "too_many_messages":
        return replace(row, messages=(api.ChatMessage("user", "x"),) * 129)
    if case == "unknown_role":
        return replace(row, messages=(api.ChatMessage("tool", "x"),))
    if case == "empty_content":
        return replace(row, messages=(api.ChatMessage("user", ""),))
    if case == "invalid_utf8":
        return replace(row, messages=(api.ChatMessage("user", "\ud800"),))
    if case == "wrong_content_type":
        return replace(row, messages=(api.ChatMessage("user", []),))
    if case == "overlong_content":
        return replace(row, messages=(api.ChatMessage("user", "x" * 65537),))
    raise AssertionError("unknown controlled case")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case",
    [
        "bool_temperature",
        "nan_temperature",
        "high_temperature",
        "negative_temperature",
        "mutable_messages",
        "empty_messages",
        "too_many_messages",
        "unknown_role",
        "empty_content",
        "invalid_utf8",
        "wrong_content_type",
        "overlong_content",
    ],
)
async def test_late_chat_input_is_rejected_before_factory(case, monkeypatch):
    monkeypatch.setattr(trace, "get_backend", lambda *a, **k: pytest.fail("backend constructed"))
    with pytest.raises(api.PlanError):
        await api.replay_trace(
            [chat_row("first"), invalid_row(case)], model="model", backend="vllm"
        )


@pytest.mark.asyncio
async def test_unsupported_chat_plugin_refuses_before_factory_and_discovery(monkeypatch):
    class LegacyOnly(Backend):
        pass

    monkeypatch.setitem(BACKEND_REGISTRY, "legacy-chat-test", LegacyOnly)
    monkeypatch.setattr(plugin, "discover_plugins", lambda: pytest.fail("plugin discovery"))
    monkeypatch.setattr(trace, "get_backend", lambda *a, **k: pytest.fail("backend constructed"))
    with pytest.raises(api.PlanError):
        await api.replay_trace([chat_row()], model="model", backend="legacy-chat-test")


@pytest.mark.asyncio
async def test_native_chat_source_path_is_held_and_cannot_be_output(saved, monkeypatch, tmp_path):
    from dataclasses import asdict

    source = tmp_path / "private-chat.json"
    raw = (json.dumps([asdict(chat_row())]) + "\n").encode()
    source.write_bytes(raw)
    monkeypatch.setattr(trace, "get_backend", lambda *a, **k: ChatObservedBackend(saved))
    candidate = saved.candidate(0)
    receipt = await api.replay_trace(
        source,
        model=candidate.model.removeprefix("ollama:"),
        backend={"llama.cpp": "ollama"}.get(candidate.backend, candidate.backend),
    )
    with pytest.raises(api.PlanError):
        receipt.save(source)
    assert source.read_bytes() == raw
