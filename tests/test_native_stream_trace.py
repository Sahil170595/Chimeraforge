"""Native stream completion and timing contracts, without a model substitute."""

from __future__ import annotations

import asyncio
import itertools
import json

import httpx
import pytest

from chimeraforge.bench.backends.sglang import SGLangBackend
from chimeraforge.bench.backends.tgi import TGIBackend
from chimeraforge.bench.backends.vllm import VLLMBackend
from chimeraforge.bench.trace import _native

CLIENT_BASIS = "client-first-to-last-native-output/(server-output-count-1)"
BACKENDS = (VLLMBackend, SGLangBackend, TGIBackend)


class Packets(httpx.AsyncByteStream):
    def __init__(self, packets):
        self.packets = packets
        self.closed = False

    async def __aiter__(self):
        for packet in self.packets:
            yield packet

    async def aclose(self):
        self.closed = True


def event(value):
    return ("data: " + json.dumps(value, ensure_ascii=False) + "\n\n").encode()


def choice(text, ids, finish=None):
    value = {"index": 0, "text": text, "finish_reason": finish}
    if ids is not None:
        value["token_ids"] = ids
    return {"choices": [value]}


def usage(count=2, prompt=7, cache=None):
    value = {"completion_tokens": count, "prompt_tokens": prompt}
    if type(count) is int and type(prompt) is int:
        value["total_tokens"] = count + prompt
    if cache is not None:
        value["prompt_tokens_details"] = {"cached_tokens": cache}
    return {"choices": [], "usage": value}


def token(text, ident=10, special=False, details=None):
    return {
        "token": {"id": ident, "text": text, "special": special},
        "details": details,
    }


def complete(backend, *, count=2, cache=None, endtext=""):
    if backend is TGIBackend:
        return [
            event(token("a")),
            event(
                token(
                    endtext,
                    11,
                    not bool(endtext),
                    {"finish_reason": "eos_token", "generated_tokens": count, "input_length": 7},
                )
            ),
        ]
    return [
        event(choice("a", [10])),
        event(choice(endtext, [11], "stop")),
        event(usage(count, cache=cache)),
        b"data: [DONE]\n\n",
    ]


def adapter(backend, packets, *, status=200):
    stream = Packets(packets)
    requests = []
    ticks = itertools.count()

    def handler(request):
        requests.append(json.loads(request.content))
        return httpx.Response(status, stream=stream)

    instance = backend(
        "http://contract.test",
        transport=httpx.MockTransport(handler),
        clock=lambda: float(next(ticks)),
    )
    return instance, stream, requests


@pytest.mark.asyncio
@pytest.mark.parametrize("backend", BACKENDS)
async def test_observation_includes_eos_in_native_interval_and_visible_callback(backend):
    instance, stream, requests = adapter(backend, complete(backend))
    first = []
    try:
        observed = await instance.generate_observed(
            "model", "private prompt", {"max_tokens": 8}, lambda: first.append(True)
        )
        assert first == [True]
        assert observed.native["tokens_generated"] == 2
        assert observed.native["prompt_tokens"] == 7
        assert observed.native["cached_prompt_tokens"] is None
        assert observed.native["ttft_ms"] == 1000
        assert observed.mean_tpot_ms == 1000 and observed.mean_tpot_basis == CLIENT_BASIS
        assert _native(observed, instance.name)[1:] == (1000, CLIENT_BASIS)
        if backend is not TGIBackend:
            assert requests[0]["return_token_ids"] is True
            assert requests[0]["echo"] is False and requests[0]["n"] == 1
            assert requests[0]["stream_options"] == {"include_usage": True}
        assert stream.closed
    finally:
        await instance.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("backend", BACKENDS)
async def test_one_coalesced_wire_packet_is_complete_without_invented_rate(backend):
    instance, stream, _ = adapter(backend, [b"".join(complete(backend, endtext="b"))])
    first = []
    try:
        observed = await instance.generate_observed("model", "p", {}, lambda: first.append(True))
        assert first == [True] and stream.closed
        assert observed.native["tokens_generated"] == 2
        assert observed.native["ttft_ms"] == 1000
        assert observed.mean_tpot_ms is None and observed.mean_tpot_basis == "unavailable"
        assert observed.native["throughput_tps"] is None
    finally:
        await instance.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("backend", BACKENDS)
async def test_single_token_completion_keeps_counts_and_available_ttft(backend):
    packets = (
        [
            event(
                token(
                    "a",
                    details={"finish_reason": "length", "generated_tokens": 1, "input_length": 7},
                )
            )
        ]
        if backend is TGIBackend
        else [event(choice("a", [10], "length")), event(usage(1)), b"data: [DONE]\n\n"]
    )
    instance, _, _ = adapter(backend, packets)
    try:
        observed = await instance.generate_observed("model", "p", {}, lambda: None)
        assert observed.native["tokens_generated"] == 1 and observed.native["ttft_ms"] == 1000
        assert observed.mean_tpot_ms is None
    finally:
        await instance.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("backend", (VLLMBackend, SGLangBackend))
async def test_absent_ids_remain_unknown_and_first_multitoken_batch_has_no_full_tpot(backend):
    for packets in (
        [
            event(choice("a", None)),
            event(choice("b", None, "stop")),
            event(usage()),
            b"data: [DONE]\n\n",
        ],
        [
            event(choice("ab", [10, 11])),
            event(choice("c", [12], "stop")),
            event(usage(3)),
            b"data: [DONE]\n\n",
        ],
    ):
        instance, _, _ = adapter(backend, packets)
        try:
            observed = await instance.generate_observed("model", "p", {}, lambda: None)
            assert observed.mean_tpot_ms is None and observed.native["throughput_tps"] is None
        finally:
            await instance.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("backend", BACKENDS)
@pytest.mark.parametrize("count", [True, "2", 2.1, -1, 3])
async def test_invalid_or_unreconciled_native_counts_are_refused(backend, count):
    instance, stream, _ = adapter(backend, complete(backend, count=count, endtext="b"))
    try:
        with pytest.raises(RuntimeError):
            await instance.generate_observed("model", "p", {}, lambda: None)
        assert stream.closed
    finally:
        await instance.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("backend", (VLLMBackend, SGLangBackend))
@pytest.mark.parametrize("defect", ["done", "finish", "usage", "abort", "error", "malformed"])
async def test_error_or_missing_terminal_proof_refuses_completion_without_private_logs(
    backend, defect, caplog
):
    packets = complete(backend, endtext="b")
    if defect == "done":
        packets = packets[:-1]
    elif defect == "finish":
        packets[1] = event(choice("b", [11]))
    elif defect == "usage":
        packets.pop(2)
    elif defect == "abort":
        packets[1] = event(choice("b", [11], "abort"))
    elif defect == "error":
        packets.insert(2, event({"error": "private-response-sentinel"}))
    else:
        packets.insert(1, b"data: private-response-sentinel\n\n")
    instance, stream, _ = adapter(backend, packets)
    try:
        with pytest.raises(RuntimeError) as raised:
            await instance.generate_observed("model", "p", {}, lambda: None)
        assert stream.closed
        assert "private-response-sentinel" not in str(raised.value) + caplog.text
    finally:
        await instance.close()


@pytest.mark.asyncio
async def test_tgi_control_token_is_not_visible_first_output_and_final_details_are_required():
    packets = [
        event(token("<s>", special=True)),
        event(
            token(
                "a",
                11,
                details={"finish_reason": "length", "generated_tokens": 2, "input_length": 7},
            )
        ),
    ]
    instance, _, _ = adapter(TGIBackend, packets)
    first = []
    try:
        observed = await instance.generate_observed("model", "p", {}, lambda: first.append(True))
        assert first == [True] and observed.native["ttft_ms"] == 2000
        assert observed.mean_tpot_ms == 1000
    finally:
        await instance.close()
    instance, stream, _ = adapter(TGIBackend, packets[:1])
    try:
        with pytest.raises(RuntimeError):
            await instance.generate_observed("model", "p", {}, lambda: None)
        assert stream.closed
    finally:
        await instance.close()


@pytest.mark.asyncio
async def test_native_stream_frame_and_http_error_bodies_are_bounded_and_private(caplog):
    for packets, status in (
        ([event(choice("private-response-sentinel" + "x" * 70000, [10]))], 200),
        ([b"private-response-sentinel" * 10000], 503),
    ):
        instance, stream, _ = adapter(VLLMBackend, packets, status=status)
        try:
            with pytest.raises((RuntimeError, httpx.HTTPStatusError)) as raised:
                await instance.generate_observed("model", "p", {}, lambda: None)
            assert stream.closed
            assert "private-response-sentinel" not in str(raised.value) + caplog.text
        finally:
            await instance.close()


@pytest.mark.asyncio
async def test_cancelled_native_stream_closes_transport():
    entered = asyncio.Event()

    class Paused(Packets):
        async def __aiter__(self):
            yield event(choice("a", [10]))
            entered.set()
            await asyncio.Event().wait()

    stream = Paused([])
    instance = VLLMBackend(
        "http://contract.test",
        transport=httpx.MockTransport(lambda _: httpx.Response(200, stream=stream)),
    )
    task = asyncio.create_task(instance.generate_observed("model", "p", {}, lambda: None))
    try:
        await asyncio.wait_for(entered.wait(), 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert stream.closed
    finally:
        await instance.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "defect",
    [
        "id-bool",
        "id-string",
        "prompt",
        "total",
        "cache",
        "conflicting-cache",
        "choice",
        "after-done",
    ],
)
async def test_native_metadata_and_choice_ambiguity_are_refused(defect):
    values = [choice("a", [10]), choice("b", [11], "stop"), usage()]
    if defect == "id-bool":
        values[0]["choices"][0]["token_ids"] = [True]
    elif defect == "id-string":
        values[0]["choices"][0]["token_ids"] = ["10"]
    elif defect == "prompt":
        values[2]["usage"]["prompt_tokens"] = "7"
    elif defect == "total":
        values[2]["usage"]["total_tokens"] = 99
    elif defect == "cache":
        values[2]["usage"]["prompt_tokens_details"] = {"cached_tokens": 8}
    elif defect == "conflicting-cache":
        values[2]["usage"]["prompt_tokens_details"] = {"cached_tokens": 2}
        values[2]["usage"]["cached_tokens"] = 1
    elif defect == "choice":
        values[0]["choices"].append({"index": 1, "text": "b", "token_ids": [12]})
    packets = [event(value) for value in values] + [b"data: [DONE]\n\n"]
    if defect == "after-done":
        packets.append(event(choice("private-response-sentinel", [12])))
    instance, stream, _ = adapter(VLLMBackend, packets)
    try:
        with pytest.raises(RuntimeError):
            await instance.generate_observed("model", "p", {}, lambda: None)
        assert stream.closed
    finally:
        await instance.close()


@pytest.mark.asyncio
async def test_fragmented_utf8_frame_uses_completing_packet_arrival_and_native_cache():
    first = event(choice("\u03c0", [10]))
    cut = first.index("\u03c0".encode()) + 1
    packets = [
        first[:cut],
        first[cut:],
        event(choice("b", [11], "stop")),
        event(usage(cache=2)),
        b"data: [DONE]\n\n",
    ]
    instance, stream, _ = adapter(VLLMBackend, packets)
    visible = []
    try:
        observed = await instance.generate_observed("model", "p", {}, lambda: visible.append(True))
        assert visible == [True] and stream.closed
        assert observed.native["ttft_ms"] == 2000 and observed.mean_tpot_ms == 1000
        assert observed.native["cached_prompt_tokens"] == 2
    finally:
        await instance.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("bound", ["bytes", "frames"])
async def test_keepalive_population_is_bounded(bound, monkeypatch):
    from chimeraforge.bench.backends import _stream_frames

    if bound == "bytes":
        monkeypatch.setattr(_stream_frames, "MAX_STREAM_BYTES", 30)
    else:
        monkeypatch.setattr(_stream_frames, "MAX_STREAM_FRAMES", 2)
    instance, stream, _ = adapter(VLLMBackend, [b": keepalive\n\n"] * 4)
    try:
        with pytest.raises(RuntimeError, match="limit"):
            await instance.generate_observed("model", "p", {}, lambda: None)
        assert stream.closed
    finally:
        await instance.close()


@pytest.mark.asyncio
async def test_buffered_frames_yield_for_cancellation_before_all_are_parsed(monkeypatch):
    from chimeraforge.bench.backends import _stream_frames

    parsed, original = [], _stream_frames.decode_frame
    stopped = asyncio.Event()

    def decode(*args):
        parsed.append(True)
        stopped.set()
        return original(*args)

    monkeypatch.setattr(_stream_frames, "decode_frame", decode)
    packets = [event(choice("a", [10])) * 1000 + event(usage(1000)) + b"data: [DONE]\n\n"]
    instance, stream, _ = adapter(VLLMBackend, packets)
    task = asyncio.create_task(instance.generate_observed("model", "p", {}, lambda: None))
    try:
        await asyncio.wait_for(stopped.wait(), 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert 0 < len(parsed) < 1000 and stream.closed
    finally:
        await instance.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("backend", BACKENDS)
async def test_native_output_cannot_exceed_requested_cap(backend):
    instance, stream, _ = adapter(backend, complete(backend))
    try:
        with pytest.raises(RuntimeError, match="requested output cap"):
            await instance.generate_observed("model", "p", {"max_tokens": 1}, lambda: None)
        assert stream.closed
    finally:
        await instance.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("backend", (VLLMBackend, SGLangBackend))
async def test_final_usage_without_ids_cannot_exceed_requested_cap(backend):
    packets = [event(choice("a", None, "length")), event(usage(2)), b"data: [DONE]\n\n"]
    instance, stream, _ = adapter(backend, packets)
    try:
        with pytest.raises(RuntimeError, match="requested output cap"):
            await instance.generate_observed("model", "p", {"max_tokens": 1}, lambda: None)
        assert stream.closed
    finally:
        await instance.close()


@pytest.mark.asyncio
async def test_tgi_native_parameter_cap_takes_precedence_over_shared_option():
    instance, stream, _ = adapter(TGIBackend, complete(TGIBackend))
    try:
        with pytest.raises(RuntimeError, match="requested output cap"):
            await instance.generate_observed(
                "model", "p", {"max_new_tokens": 1, "max_tokens": 8}, lambda: None
            )
        assert stream.closed
    finally:
        await instance.close()
