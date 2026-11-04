"""Native text-chat replay retains roles and never infers token counts from chunks."""

from dataclasses import asdict
import json

import httpx
import pytest

from chimeraforge import api
from chimeraforge.bench.backends.vllm import VLLMBackend
from chimeraforge.bench.trace_workload import load_workload
from test_native_stream_trace import Packets, adapter, complete, event


@pytest.mark.asyncio
async def test_native_legacy_completion_and_four_field_workload_remain_supported():
    row = api.TraceRequest("legacy", "private legacy prompt", 8, 0)
    held, identity, _ = load_workload([row])
    assert held == [row] and identity["canonical_sha256"]
    assert set(asdict(row)) == {"request_id", "prompt", "max_output_tokens", "arrival_offset_s"}
    backend, stream, sent = adapter(VLLMBackend, complete(VLLMBackend))
    try:
        observation = await backend.generate_observed(
            "model", row.prompt, {"max_tokens": 8}, lambda: None
        )
        assert observation.native["tokens_generated"] == 2
        assert sent[0]["prompt"] == row.prompt and "messages" not in sent[0]
    finally:
        await backend.close()
    assert stream.closed and backend._client.is_closed


def test_public_typed_chat_workload_preserves_message_roles_and_order():
    messages = (
        api.ChatMessage("system", "private system \u03bb"),
        api.ChatMessage("user", "private question"),
        api.ChatMessage("assistant", "private earlier answer"),
        api.ChatMessage("user", "private next question"),
    )
    row = api.ChatTraceRequest("chat", messages, 8, 0)
    held, identity, _ = load_workload([row])
    assert held == [row] and identity["canonical_sha256"]
    assert [item.role for item in held[0].messages] == ["system", "user", "assistant", "user"]
    assert held[0].messages == messages
    assert asdict(row)["mode"] == "chat"


@pytest.mark.asyncio
async def test_native_chat_endpoint_role_only_delta_and_missing_usage_are_not_tokens():
    messages = [
        {"role": "system", "content": "private instructions"},
        {"role": "user", "content": "private question"},
    ]
    packets = [
        event(
            {
                "choices": [
                    {
                        "index": 0,
                        "delta": {"role": "assistant", "content": ""},
                        "finish_reason": None,
                    }
                ]
            }
        ),
        event(
            {
                "choices": [
                    {"index": 0, "delta": {"content": "private answer"}, "finish_reason": None}
                ]
            }
        ),
        event({"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}),
        b"data: [DONE]\n\n",
    ]
    stream = Packets([byte for packet in packets for byte in (packet[:7], packet[7:])])
    seen = []
    first = []

    def handler(request):
        seen.append((request.url.path, json.loads(request.content)))
        return httpx.Response(200, stream=stream)

    backend = VLLMBackend("http://controlled.invalid", transport=httpx.MockTransport(handler))
    try:
        observed = await backend.chat_observed(
            "model", messages, {"max_tokens": 8, "temperature": 0.0}, lambda: first.append(True)
        )
        assert first == [True]
        assert observed.native["tokens_generated"] is None
        assert observed.native["prompt_tokens"] is None and observed.mean_tpot_ms is None
        assert seen[0][0] == "/v1/chat/completions"
        assert seen[0][1]["messages"] == messages
        assert not {"prompt", "echo", "return_token_ids"} & set(seen[0][1])
    finally:
        await backend.close()
    assert stream.closed and backend._client.is_closed


def chat_row(ident="chat", **changes):
    from dataclasses import replace

    return replace(
        api.ChatTraceRequest(
            ident,
            (
                api.ChatMessage("system", "private exact instructions"),
                api.ChatMessage("user", f"private exact question {ident}"),
            ),
            8,
            0,
        ),
        **changes,
    )


def chat_frames():
    return [
        event({"choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}]}),
        event(
            {
                "choices": [
                    {"index": 0, "delta": {"content": "private completion"}, "finish_reason": None}
                ]
            }
        ),
        event({"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}),
        b"data: [DONE]\n\n",
    ]


@pytest.mark.asyncio
async def test_whole_native_chat_replay_saved_receiving_and_private_commitments(
    tmp_path, monkeypatch
):
    import chimeraforge.bench.trace as trace
    from chimeraforge.bench.trace_gate_inputs import load_trace

    sent = []
    streams = []

    def handler(request):
        if request.method == "POST":
            sent.append((request.url.path, json.loads(request.content)))
            stream = Packets(chat_frames())
            streams.append(stream)
            return httpx.Response(200, stream=stream)
        if request.url.path == "/health":
            return httpx.Response(200)
        if request.url.path == "/version":
            return httpx.Response(200, json={"version": "0.30.0"})
        if request.url.path == "/v1/models":
            return httpx.Response(200, json={"data": [{"id": "model"}]})
        return httpx.Response(404, json={})

    backend = VLLMBackend("http://controlled.invalid", transport=httpx.MockTransport(handler))
    monkeypatch.setattr(trace, "get_backend", lambda *args, **kwargs: backend)
    rows = [chat_row("first"), chat_row("second")]
    receipt = await api.replay_trace(
        rows, model="model", backend="vllm", concurrency=2, request_timeout=2, trace_timeout=5
    )
    data = receipt.to_dict()
    assert data["execution"]["planned"] == data["execution"]["completed"] == 2
    assert data["exit_code"] == 0 and data["resource_cleanup"]["state"] == "completed"
    assert [item[0] for item in sent] == ["/v1/chat/completions"] * 2
    assert sent[0][1]["messages"] == [asdict(m) for m in rows[0].messages]
    for row in data["requests"]:
        assert row["descriptor"]["mode"] == "chat"
        assert row["native"]["tokens_generated"] is None
        assert row["native"]["prompt_tokens"] is None and row["mean_tpot_ms"] is None
    assert "private exact" not in json.dumps(data) and "private completion" not in json.dumps(data)
    path = tmp_path / "chat-trace.json"
    receipt.save(path)
    assert load_trace(path)["data"] == data
    assert all(stream.closed for stream in streams) and backend._client.is_closed


@pytest.mark.asyncio
async def test_late_invalid_chat_and_unsupported_plugin_refuse_before_any_factory(monkeypatch):
    import chimeraforge.bench.trace as trace

    calls = []
    monkeypatch.setattr(trace, "get_backend", lambda *a, **k: calls.append(True))
    invalid = chat_row("last", messages=(api.ChatMessage("tool", "private unsupported"),))
    with pytest.raises(api.PlanError):
        await api.replay_trace([chat_row(), invalid], model="model", backend="vllm")
    with pytest.raises(api.PlanError):
        await api.replay_trace([chat_row()], model="model", backend="unloaded-plugin")
    assert calls == []


@pytest.mark.asyncio
async def test_native_ollama_chat_exact_history_flags_and_omitted_counters():
    from chimeraforge.bench.backends.ollama import OllamaBackend

    sent = []
    stream = Packets(
        [
            (
                json.dumps({"message": {"role": "assistant", "content": "answer"}, "done": False})
                + "\n"
            ).encode(),
            (
                json.dumps(
                    {
                        "message": {"role": "assistant", "content": ""},
                        "done": True,
                        "done_reason": "stop",
                    }
                )
                + "\n"
            ).encode(),
        ]
    )

    def handler(request):
        sent.append((request.url.path, json.loads(request.content)))
        return httpx.Response(200, stream=stream)

    backend = OllamaBackend("http://controlled.invalid")
    backend._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    messages = [{"role": "user", "content": "private complete message"}]
    first = []
    try:
        value = await backend.chat_observed(
            "model", messages, {"num_predict": 8, "temperature": 0}, lambda: first.append(True)
        )
        assert value.native["tokens_generated"] is None and value.native["prompt_tokens"] is None
        assert value.native["eval_duration_ms"] is None and value.mean_tpot_ms is None
        assert first == [True] and sent[0][0] == "/api/chat"
        assert sent[0][1]["messages"] == messages
        assert all(sent[0][1][name] is False for name in ("think", "truncate", "shift"))
    finally:
        await backend.close()
    assert stream.closed and backend._client.is_closed


def test_chat_logical_byte_budget_refuses_before_whole_workload_encoding(monkeypatch):
    import chimeraforge.bench.trace_workload as workload

    shared = "x" * workload.MAX_PROMPT_BYTES
    rows = [chat_row(str(i), messages=(api.ChatMessage("user", shared),)) for i in range(129)]
    original = workload.json.dumps
    whole_encoding = []

    def bounded_encode(value, *args, **kwargs):
        if type(value) is list and len(value) == len(rows):
            whole_encoding.append(True)
            raise RuntimeError("whole oversized workload encoded before admission")
        return original(value, *args, **kwargs)

    monkeypatch.setattr(workload.json, "dumps", bounded_encode)
    with pytest.raises(api.PlanError):
        workload.load_workload(rows)
    assert whole_encoding == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "changes, completed",
    [
        ({"prompt_eval_cached_count": 2}, False),
        ({"eval_duration": 0}, True),
        ({"prompt_eval_count": 2**31}, False),
        ({"omit_prompt_count": True}, True),
        ({"prompt_eval_count": 2, "prompt_eval_cached_count": 1}, True),
    ],
)
async def test_ollama_inconsistent_chat_cache_refuses_before_saved_receipt_contradiction(
    tmp_path, monkeypatch, changes, completed
):
    import chimeraforge.bench.trace as trace
    from chimeraforge.bench.backends.ollama import OllamaBackend
    from chimeraforge.bench.trace_gate_inputs import load_trace

    terminal = {
        "message": {"role": "assistant", "content": "answer"},
        "done": True,
        "done_reason": "stop",
        "eval_count": 1,
        "eval_duration": 1000000,
        "prompt_eval_count": 1,
        "prompt_eval_cached_count": 0,
    }
    terminal.update(changes)
    if terminal.pop("omit_prompt_count", False):
        terminal.pop("prompt_eval_count")
    stream = Packets([(json.dumps(terminal) + "\n").encode()])

    def handler(request):
        if request.url.path == "/api/chat":
            return httpx.Response(200, stream=stream)
        if request.url.path == "/":
            return httpx.Response(200, text="Ollama is running")
        if request.url.path == "/api/version":
            return httpx.Response(200, json={"version": "0.35.1"})
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "model"}]})
        return httpx.Response(200, json={})

    backend = OllamaBackend("http://controlled.invalid")
    backend._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(trace, "get_backend", lambda *args, **kwargs: backend)
    receipt = await api.replay_trace(
        [chat_row()], model="model", backend="ollama", request_timeout=2, trace_timeout=5
    )
    path = tmp_path / "cache-count-receipt.json"
    receipt.save(path)
    loaded = load_trace(path)["data"]
    assert loaded["execution"]["completed"] == int(completed)
    if not completed:
        assert loaded["execution"]["partial"] + loaded["execution"]["failed"] == 1
        assert loaded["requests"][0]["native"]["cached_prompt_tokens"] is None
    if changes.get("eval_duration") == 0:
        assert loaded["requests"][0]["native"]["eval_duration_ms"] == 0
        assert loaded["requests"][0]["mean_tpot_ms"] is None
    if changes.get("omit_prompt_count"):
        assert loaded["requests"][0]["native"]["prompt_tokens"] is None
        assert loaded["requests"][0]["native"]["cached_prompt_tokens"] == 0
    assert stream.closed and backend._client.is_closed


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "details, refused",
    [
        ({}, False),
        ({"reasoning_tokens": 0}, False),
        ({"completion_tokens_details": {"reasoning_tokens": 0, "audio_tokens": 0}}, False),
        ({"reasoning_tokens": 1}, True),
        ({"completion_tokens_details": {"reasoning_tokens": 1}}, True),
        ({"completion_tokens_details": {"audio_tokens": 1}}, True),
        ({"reasoning_tokens": True}, True),
    ],
)
async def test_plain_chat_profile_admits_unknown_or_zero_but_not_known_nontext_usage(
    details, refused
):
    usage = {"completion_tokens": 2, "prompt_tokens": 7, "total_tokens": 9, **details}
    packets = chat_frames()
    packets.insert(-1, event({"choices": [], "usage": usage}))
    stream = Packets(packets)
    backend = VLLMBackend(
        "http://controlled.invalid",
        transport=httpx.MockTransport(lambda request: httpx.Response(200, stream=stream)),
    )
    try:
        operation = backend.chat_observed(
            "model", [{"role": "user", "content": "private"}], {"max_tokens": 8}, lambda: None
        )
        if refused:
            with pytest.raises(RuntimeError):
                await operation
        else:
            observed = await operation
            assert observed.native["tokens_generated"] == 2 and observed.mean_tpot_ms is None
    finally:
        await backend.close()
    assert stream.closed and backend._client.is_closed
