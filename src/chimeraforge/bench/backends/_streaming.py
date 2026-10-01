"""Streamed generation timing shared by the bench adapters.

The planner predicts a single-stream DECODE rate. Completion tokens over wall
clock -- what a non-streaming request can report -- folds prefill into that
number and under-reports decode more as the prompt grows. Streaming lets an
adapter time the first and last token, so decode is (tokens - 1) over the
interval between them and TTFT is reported separately.

Token counts always come from the server (a usage block, or the final details),
never from counting chunks: one chunk can carry several tokens.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass

import httpx

from chimeraforge.bench.metrics import RunMetrics

logger = logging.getLogger(__name__)

SSE_PREFIX = "data:"
SSE_DONE = "[DONE]"


def parse_sse(line: str, engine: str) -> dict | None:
    """One SSE ``data:`` line -> its JSON payload; None for keep-alives and [DONE]."""
    line = line.strip()
    if not line.startswith(SSE_PREFIX):
        return None
    data = line[len(SSE_PREFIX) :].strip()
    if not data or data == SSE_DONE:
        return None
    try:
        return json.loads(data)
    except json.JSONDecodeError:
        logger.warning("%s sent an unparseable stream line: %.120s", engine, data)
        return None


@dataclass
class StreamTiming:
    """What a streamed request observed, before it becomes RunMetrics."""

    t0: float
    t_first: float | None = None
    t_last: float | None = None
    t_end: float = 0.0
    tokens: int | None = None  # as the server reported it

    def mark_token(self, now: float) -> None:
        if self.t_first is None:
            self.t_first = now
        self.t_last = now


def decode_metrics(timing: StreamTiming, engine: str, count_source: str) -> RunMetrics:
    """Turn a stream's timing into RunMetrics, or fail the run rather than guess.

    Raises:
        RuntimeError: The server reported no token count, or too few tokens
            arrived at distinct times to time a decode.
    """
    if timing.tokens is None:
        raise RuntimeError(
            f"{engine} returned no {count_source}, so the generated token count is "
            "unknown; the run is discarded rather than estimated"
        )
    tokens = int(timing.tokens)
    first, last = timing.t_first, timing.t_last
    if tokens < 2 or first is None or last is None or last <= first:
        raise RuntimeError(
            f"{tokens} token(s) streamed: a decode rate needs at least two tokens "
            "arriving at distinct times. Raise max_tokens."
        )
    ttft_ms = (first - timing.t0) * 1000
    decode_s = last - first
    return RunMetrics(
        tokens_generated=tokens,
        # The first token is produced by prefill; the remaining tokens - 1 arrive
        # over the decode interval.
        throughput_tps=(tokens - 1) / decode_s,
        ttft_ms=ttft_ms,
        total_duration_ms=(timing.t_end - timing.t0) * 1000,
        prompt_eval_duration_ms=ttft_ms,
        eval_duration_ms=decode_s * 1000,
    )


async def stream_openai_completion(
    client: httpx.AsyncClient,
    url: str,
    payload: dict,
    clock: Callable[[], float],
    engine: str,
    timeout: float,
) -> RunMetrics:
    """POST an OpenAI-compatible ``/v1/completions`` request streamed with
    ``stream_options.include_usage`` (vLLM and SGLang both emit the usage block
    in a final chunk with empty ``choices``), and time it."""
    body = {**payload, "stream": True, "stream_options": {"include_usage": True}}
    timing = StreamTiming(t0=clock())
    async with client.stream("POST", url, json=body, timeout=timeout) as resp:
        if resp.status_code >= 400:
            await resp.aread()
            resp.raise_for_status()
        async for line in resp.aiter_lines():
            chunk = parse_sse(line, engine)
            if chunk is None:
                continue
            usage = chunk.get("usage")
            if usage and usage.get("completion_tokens") is not None:
                timing.tokens = usage["completion_tokens"]
            if any(c.get("text") for c in chunk.get("choices") or []):
                timing.mark_token(clock())
    timing.t_end = clock()
    return decode_metrics(timing, engine, "usage block")
