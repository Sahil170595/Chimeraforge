"""Tagged native chat shapes through each adapter, without an inference engine."""

import pytest

from chimeraforge.bench.backends.vllm import VLLMBackend
from chimeraforge.bench.backends.sglang import SGLangBackend
from chimeraforge.bench.backends.tgi import TGIBackend
from chimeraforge.bench.backends._stream_frames import MAX_FRAME_BYTES, StreamProtocolError
from test_native_stream_trace import adapter, event, usage

BACKENDS = (VLLMBackend, SGLangBackend, TGIBackend)
MESSAGES = [
    {"role": "system", "content": "private system"},
    {"role": "user", "content": "private question"},
]
DONE = b"data: [DONE]\n\n"


def choice(delta, finish=None, index=0):
    return event({"choices": [{"index": index, "delta": delta, "finish_reason": finish}]})


@pytest.mark.asyncio
@pytest.mark.parametrize("backend", BACKENDS)
async def test_native_chat_utf8_fragmented_usage_and_role_only_first_event(backend):
    raw = choice({"role": "assistant", "content": ""})
    raw += choice({"content": "private output \u03bb"}) + choice({}, "stop") + event(usage()) + DONE
    instance, stream, sent = adapter(backend, [raw[i : i + 1] for i in range(len(raw))])
    first = []
    try:
        observed = await instance.chat_observed(
            "model", MESSAGES, {"max_tokens": 8, "temperature": 0.25}, lambda: first.append(True)
        )
        assert first == [True]
        assert observed.native["tokens_generated"] == 2
        assert observed.native["prompt_tokens"] == 7
        assert observed.native["cached_prompt_tokens"] is None
        assert observed.mean_tpot_ms is None
        assert sent[0]["messages"] == MESSAGES and sent[0]["temperature"] == 0.25
        assert sent[0]["stream_options"] == {"include_usage": True}
        assert not {"echo", "return_token_ids", "return_prompt_token_ids", "prompt"} & set(sent[0])
    finally:
        await instance.close()
    assert stream.closed and instance._client.is_closed


def invalid_packets(case):
    text, finish = choice({"content": "private output"}), choice({}, "stop")
    if case == "missing_done":
        return [text, finish]
    if case == "missing_finish":
        return [text, DONE]
    if case == "tool_delta":
        return [choice({"tool_calls": [{"id": "private"}]}), finish, DONE]
    if case == "reasoning_delta":
        return [choice({"reasoning_content": "private"}), finish, DONE]
    if case == "audio_delta":
        return [choice({"audio": {"data": "private"}}), finish, DONE]
    if case == "multimodal_content":
        return [choice({"content": [{"text": "private"}]}), finish, DONE]
    if case == "wrong_role":
        return [choice({"role": "tool", "content": "private"}), finish, DONE]
    if case == "wrong_index":
        return [choice({"content": "private"}, index=1), finish, DONE]
    if case == "multiple_choices":
        return [event({"choices": [{"index": 0, "delta": {}}, {"index": 1, "delta": {}}]}), DONE]
    if case == "tool_finish":
        return [text, choice({}, "tool_calls"), DONE]
    if case == "early_usage":
        return [event(usage()), text, finish, DONE]
    if case == "bool_count":
        return [text, finish, event(usage(True)), DONE]
    if case == "cap_exceeded":
        return [text, finish, event(usage(9)), DONE]
    if case == "after_done":
        return [text, finish, DONE, text]
    if case == "oversized_frame":
        return [b"data: " + b"x" * (MAX_FRAME_BYTES + 1) + b"\n\n"]
    if case == "reasoning_usage":
        return [text, finish, event({"choices": [], "usage": {"reasoning_tokens": 1}}), DONE]
    raise AssertionError("unknown controlled case")


@pytest.mark.asyncio
@pytest.mark.parametrize("backend", BACKENDS)
@pytest.mark.parametrize(
    "case",
    [
        "missing_done",
        "missing_finish",
        "tool_delta",
        "reasoning_delta",
        "audio_delta",
        "multimodal_content",
        "wrong_role",
        "wrong_index",
        "multiple_choices",
        "tool_finish",
        "early_usage",
        "bool_count",
        "cap_exceeded",
        "after_done",
        "oversized_frame",
        "reasoning_usage",
    ],
)
async def test_native_chat_refuses_unsupported_or_incomplete_wire_and_closes(backend, case):
    instance, stream, _ = adapter(backend, invalid_packets(case))
    try:
        with pytest.raises(StreamProtocolError):
            await instance.chat_observed("model", MESSAGES, {"max_tokens": 8}, lambda: None)
    finally:
        await instance.close()
    assert stream.closed and instance._client.is_closed
