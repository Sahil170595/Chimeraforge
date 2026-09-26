"""vLLM and TGI bench adapters report the DECODE rate the planner predicts.

Both reported completion tokens over wall clock -- prefill included -- and
`measure` filed that into the corpus as a decode rate, understating decode more
as the prompt grew. (vLLM's and TGI's `generate` had no tests at all.) They now
stream, like the SGLang adapter: TTFT is the first token, decode is
(tokens - 1) over the first-to-last interval, and the token count comes from the
server, never from counting chunks.

Formats read from source at vLLM v0.30.0 (usage in a final chunk with empty
choices, then [DONE]) and TGI v3.3.7 (StreamResponse events; the last carries
details.generated_tokens; no [DONE]).
"""

from __future__ import annotations

import json

import httpx
import pytest

from chimeraforge.bench.backends.tgi import TGIBackend
from chimeraforge.bench.backends.vllm import VLLMBackend


class _Clock:
    def __init__(self, ticks):
        self._ticks = list(ticks)

    def __call__(self):
        return self._ticks.pop(0)


def _sse(events, done=True) -> bytes:
    body = "".join(f"data: {json.dumps(e)}\n\n" for e in events)
    return (body + ("data: [DONE]\n\n" if done else "")).encode("utf-8")


def _vllm(handler, clock=None):
    return VLLMBackend("http://vllm.test:8000", transport=httpx.MockTransport(handler), clock=clock)


def _tgi(handler, clock=None):
    return TGIBackend("http://tgi.test:8080", transport=httpx.MockTransport(handler), clock=clock)


def _text(t):
    return {"choices": [{"index": 0, "text": t}]}


def _usage(n):
    return {
        "choices": [],
        "usage": {"prompt_tokens": 7, "completion_tokens": n, "total_tokens": 7 + n},
    }


def _tgi_token(text, special=False, details=None):
    event = {
        "index": 0,
        "token": {"id": 1, "text": text, "logprob": -0.1, "special": special},
        "top_tokens": [],
        "generated_text": None,
        "details": None,
    }
    if details is not None:
        event["generated_text"] = "done"
        event["details"] = details
    return event


class TestVLLM:
    @pytest.mark.asyncio
    async def test_decode_rate_excludes_prefill(self):
        """5 tokens: first at 0.1 s, last at 0.5 s, done at 0.6 s -> 4 / 0.4 = 10 tok/s.
        The old wall-clock rate was 5 / 0.6 = 8.3."""
        body = _sse([_text(c) for c in "abcde"] + [_usage(5)])
        m = await _vllm(
            lambda r: httpx.Response(200, content=body), _Clock([0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6])
        ).generate("m", "p")
        assert m.throughput_tps == pytest.approx(10.0)
        assert m.ttft_ms == pytest.approx(100.0)
        assert m.total_duration_ms == pytest.approx(600.0)

    @pytest.mark.asyncio
    async def test_request_streams_and_asks_for_usage(self):
        seen = {}

        def handler(req):
            seen.update(json.loads(req.content))
            return httpx.Response(200, content=_sse([_text("a"), _text("b"), _usage(2)]))

        await _vllm(handler, _Clock([0, 1, 2, 3])).generate("m", "p", {"max_tokens": 32})
        assert seen["stream"] is True
        assert seen["stream_options"] == {"include_usage": True}
        assert seen["max_tokens"] == 32

    @pytest.mark.asyncio
    async def test_no_usage_is_a_failed_run(self):
        body = _sse([_text("a"), _text("b")])
        with pytest.raises(RuntimeError, match="usage"):
            await _vllm(lambda r: httpx.Response(200, content=body), _Clock([0, 1, 2, 3])).generate(
                "m", "p"
            )


class TestTGI:
    @pytest.mark.asyncio
    async def test_decode_rate_from_generate_stream(self):
        events = [_tgi_token(c) for c in "abcd"] + [
            _tgi_token(
                "e", details={"finish_reason": "length", "generated_tokens": 5, "input_length": 7}
            )
        ]
        m = await _tgi(
            lambda r: httpx.Response(200, content=_sse(events, done=False)),
            _Clock([0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6]),
        ).generate("m", "p")
        assert m.tokens_generated == 5
        assert m.throughput_tps == pytest.approx(10.0)
        assert m.ttft_ms == pytest.approx(100.0)

    @pytest.mark.asyncio
    async def test_special_tokens_are_not_content_arrivals(self):
        """A leading special token (e.g. BOS) must not start the decode clock."""
        events = [
            _tgi_token("<s>", special=True),
            _tgi_token("a"),
            _tgi_token("b", details={"finish_reason": "eos_token", "generated_tokens": 2}),
        ]
        # ticks: t0, "a", "b", end  (the special token takes no tick)
        m = await _tgi(
            lambda r: httpx.Response(200, content=_sse(events, done=False)),
            _Clock([0, 0.2, 0.4, 0.5]),
        ).generate("m", "p")
        assert m.ttft_ms == pytest.approx(200.0)
        assert m.throughput_tps == pytest.approx(1 / 0.2)

    @pytest.mark.asyncio
    async def test_request_asks_for_details_on_the_stream_route(self):
        seen = {}

        def handler(req):
            seen["path"] = req.url.path
            seen.update(json.loads(req.content))
            events = [_tgi_token("a"), _tgi_token("b", details={"generated_tokens": 2})]
            return httpx.Response(200, content=_sse(events, done=False))

        await _tgi(handler, _Clock([0, 1, 2, 3])).generate("m", "p")
        assert seen["path"] == "/generate_stream"
        assert seen["parameters"]["details"] is True

    @pytest.mark.asyncio
    async def test_no_final_details_is_a_failed_run(self):
        events = [_tgi_token("a"), _tgi_token("b")]
        with pytest.raises(RuntimeError, match="generated_tokens"):
            await _tgi(
                lambda r: httpx.Response(200, content=_sse(events, done=False)),
                _Clock([0, 1, 2, 3]),
            ).generate("m", "p")

    @pytest.mark.asyncio
    async def test_http_error_propagates(self):
        with pytest.raises(httpx.HTTPStatusError):
            await _tgi(lambda r: httpx.Response(422, json={"error": "bad"})).generate("m", "p")
