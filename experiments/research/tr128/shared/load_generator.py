"""TR128 core async load generator infrastructure.

Provides arrival pattern generators, batch/stream request executors,
queue depth tracking, and multi-turn conversation support.

Key design decisions:
- Queue depth tracked via mutable ``[0]`` list (safe in single-threaded asyncio)
- Queue wait = wall_ms - (prompt_eval_ms + eval_ms + load_duration_ms)
- Each request gets its own httpx.AsyncClient to avoid connection pool contention
- Streaming measurement reports **inter-chunk** latency (ichunk), NOT inter-token.
  TCP buffering means Ollama may batch multiple tokens per network read.
  TTFT *is* reliable (first non-empty chunk always marks first generated token).
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
import json
import logging
import time

import httpx
import numpy as np

log = logging.getLogger("tr128.load_generator")

_QUEUE_DEPTH_WARNING = 20


@dataclass
class RequestResult:
    """Captures all timing and metadata for a single request."""

    request_id: int = 0
    wall_ms: float = 0.0
    ttft_ms: float | None = None
    # Inter-CHUNK latencies (not inter-token — TCP buffering caveat)
    ichunk_values_ms: list[float] = field(default_factory=list)
    queue_depth_at_submit: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    prompt_eval_ms: float = 0.0
    eval_ms: float = 0.0
    total_duration_ms: float = 0.0
    load_duration_ms: float = 0.0
    tokens_per_s: float = 0.0
    response_text: str = ""
    status: str = "ok"


# ── Arrival pattern generators ────────────────────────────────────────


async def poisson_arrivals(
    n: int,
    rate: float,
    rng: np.random.Generator | None = None,
) -> AsyncIterator[float]:
    """Yield *n* inter-arrival delays drawn from Exp(1/rate)."""
    if rate <= 0:
        raise ValueError(f"rate must be positive, got {rate}")
    if rng is None:
        rng = np.random.default_rng(42)
    delays = rng.exponential(1.0 / rate, size=n)
    for d in delays:
        yield float(d)


async def bursty_arrivals(
    n: int,
    rate: float,
    burst_size: int = 3,
    burst_gap: float = 0.05,
    rng: np.random.Generator | None = None,
) -> AsyncIterator[float]:
    """Bursts of *burst_size* rapid requests separated by longer gaps."""
    if rng is None:
        rng = np.random.default_rng(42)
    emitted = 0
    while emitted < n:
        for i in range(min(burst_size, n - emitted)):
            if i == 0 and emitted > 0:
                yield float(rng.exponential(burst_size / rate))
            else:
                yield burst_gap
            emitted += 1


async def periodic_arrivals(
    n: int,
    rate: float,
    **_kwargs,
) -> AsyncIterator[float]:
    """Constant inter-arrival delays at exactly *rate* req/s."""
    if rate <= 0:
        raise ValueError(f"rate must be positive, got {rate}")
    delay = 1.0 / rate
    for _ in range(n):
        yield delay


async def timed_periodic_arrivals(
    duration_s: float,
    rate: float,
) -> AsyncIterator[float]:
    """Yield delays for *duration_s* seconds at *rate* req/s.

    Used by Phase 3 (thermal) where we run for a fixed duration,
    not a fixed number of requests.
    """
    if rate <= 0:
        raise ValueError(f"rate must be positive, got {rate}")
    delay = 1.0 / rate
    n = int(duration_s * rate) + 1
    for _ in range(n):
        yield delay


# ── Request executors ─────────────────────────────────────────────────


def _extract_ollama_timing(data: dict) -> dict:
    """Extract Ollama native timing (nanoseconds → ms)."""
    ns_to_ms = 1e-6
    return {
        "prompt_tokens": data.get("prompt_eval_count", 0),
        "completion_tokens": data.get("eval_count", 0),
        "prompt_eval_ms": data.get("prompt_eval_duration", 0) * ns_to_ms,
        "eval_ms": data.get("eval_duration", 0) * ns_to_ms,
        "total_duration_ms": data.get("total_duration", 0) * ns_to_ms,
        "load_duration_ms": data.get("load_duration", 0) * ns_to_ms,
    }


async def execute_batch_request(
    client: httpx.AsyncClient,
    url: str,
    model: str,
    prompt: str,
    max_tokens: int = 128,
    timeout: float = 120.0,
) -> RequestResult:
    """POST to /api/generate with stream=false."""
    result = RequestResult()
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_predict": max_tokens,
            "temperature": 0.0,
            "seed": 42,
        },
    }
    t0 = time.perf_counter()
    try:
        resp = await client.post(
            f"{url}/api/generate",
            json=payload,
            timeout=timeout,
        )
        result.wall_ms = (time.perf_counter() - t0) * 1000.0
        resp.raise_for_status()
        data = resp.json()

        timing = _extract_ollama_timing(data)
        result.prompt_tokens = timing["prompt_tokens"]
        result.completion_tokens = timing["completion_tokens"]
        result.prompt_eval_ms = timing["prompt_eval_ms"]
        result.eval_ms = timing["eval_ms"]
        result.total_duration_ms = timing["total_duration_ms"]
        result.load_duration_ms = timing["load_duration_ms"]
        result.response_text = data.get("response", "")

        if result.eval_ms > 0 and result.completion_tokens > 0:
            result.tokens_per_s = result.completion_tokens / (result.eval_ms / 1000.0)
    except httpx.TimeoutException:
        result.wall_ms = (time.perf_counter() - t0) * 1000.0
        result.status = "timeout"
    except Exception as exc:
        result.wall_ms = (time.perf_counter() - t0) * 1000.0
        result.status = f"error: {exc}"
        log.warning("Batch request %s failed: %s", model, exc)

    return result


async def execute_stream_request(
    client: httpx.AsyncClient,
    url: str,
    model: str,
    prompt: str,
    max_tokens: int = 128,
    timeout: float = 120.0,
) -> RequestResult:
    """POST to /api/generate with stream=true.

    Measures TTFT (time to first non-empty chunk) and inter-chunk latencies.
    NOTE: inter-chunk != inter-token due to TCP buffering. TTFT IS reliable.
    """
    result = RequestResult()
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": True,
        "options": {
            "num_predict": max_tokens,
            "temperature": 0.0,
            "seed": 42,
        },
    }
    t0 = time.perf_counter()
    try:
        async with client.stream(
            "POST",
            f"{url}/api/generate",
            json=payload,
            timeout=timeout,
        ) as resp:
            resp.raise_for_status()
            first_chunk = True
            prev_time = t0
            full_response = []

            async for line in resp.aiter_lines():
                if not line.strip():
                    continue
                now = time.perf_counter()

                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    log.debug("Malformed stream chunk: %s", line[:80])
                    continue

                if first_chunk and chunk.get("response"):
                    result.ttft_ms = (now - t0) * 1000.0
                    first_chunk = False
                    prev_time = now
                elif not first_chunk and chunk.get("response"):
                    ichunk = (now - prev_time) * 1000.0
                    result.ichunk_values_ms.append(ichunk)
                    prev_time = now

                if chunk.get("response"):
                    full_response.append(chunk["response"])

                if chunk.get("done"):
                    timing = _extract_ollama_timing(chunk)
                    result.prompt_tokens = timing["prompt_tokens"]
                    result.completion_tokens = timing["completion_tokens"]
                    result.prompt_eval_ms = timing["prompt_eval_ms"]
                    result.eval_ms = timing["eval_ms"]
                    result.total_duration_ms = timing["total_duration_ms"]
                    result.load_duration_ms = timing["load_duration_ms"]

            result.wall_ms = (time.perf_counter() - t0) * 1000.0
            result.response_text = "".join(full_response)

            if result.eval_ms > 0 and result.completion_tokens > 0:
                result.tokens_per_s = result.completion_tokens / (
                    result.eval_ms / 1000.0
                )

    except httpx.TimeoutException:
        result.wall_ms = (time.perf_counter() - t0) * 1000.0
        result.status = "timeout"
    except Exception as exc:
        result.wall_ms = (time.perf_counter() - t0) * 1000.0
        result.status = f"error: {exc}"
        log.warning("Stream request %s failed: %s", model, exc)

    return result


# ── Load test runner ──────────────────────────────────────────────────


async def run_load_test(
    url: str,
    model: str,
    prompts: list[str],
    arrival_gen: AsyncIterator[float],
    executor: str = "batch",
    max_tokens: int = 128,
    timeout: float = 120.0,
) -> list[RequestResult]:
    """Submit requests per arrival pattern, track queue depth."""
    if not prompts:
        log.warning("run_load_test called with empty prompt list")
        return []

    results: list[RequestResult] = []
    in_flight = [0]
    max_depth_seen = [0]
    tasks: list[asyncio.Task] = []

    async def _submit(idx: int, prompt: str) -> None:
        depth = in_flight[0]
        in_flight[0] += 1
        if in_flight[0] > max_depth_seen[0]:
            max_depth_seen[0] = in_flight[0]
        if in_flight[0] >= _QUEUE_DEPTH_WARNING:
            log.warning("Queue depth %d at request %d", in_flight[0], idx)
        try:
            async with httpx.AsyncClient() as client:
                if executor == "stream":
                    r = await execute_stream_request(
                        client,
                        url,
                        model,
                        prompt,
                        max_tokens,
                        timeout,
                    )
                else:
                    r = await execute_batch_request(
                        client,
                        url,
                        model,
                        prompt,
                        max_tokens,
                        timeout,
                    )
            r.request_id = idx
            r.queue_depth_at_submit = depth
            results.append(r)
        finally:
            in_flight[0] -= 1

    idx = 0
    async for delay in arrival_gen:
        if idx >= len(prompts):
            break
        await asyncio.sleep(delay)
        tasks.append(asyncio.create_task(_submit(idx, prompts[idx])))
        idx += 1

    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)

    n_ok = sum(1 for r in results if r.status == "ok")
    log.info(
        "Load test: %d/%d ok, max queue depth %d",
        n_ok,
        len(results),
        max_depth_seen[0],
    )
    results.sort(key=lambda r: r.request_id)
    return results


# ── Multi-turn conversation executor ─────────────────────────────────


async def run_multiturn_conversation(
    url: str,
    model: str,
    user_prompts: list[str],
    context_strategy: str = "full",
    sliding_window: int = 3,
    max_tokens: int = 128,
    timeout: float = 120.0,
) -> list[RequestResult]:
    """Sequential turns via /api/chat with message history."""
    if not user_prompts:
        return []

    results: list[RequestResult] = []
    messages: list[dict] = []
    consecutive_errors = 0

    async with httpx.AsyncClient() as client:
        for turn_idx, user_msg in enumerate(user_prompts):
            messages.append({"role": "user", "content": user_msg})

            context = (
                messages[-(sliding_window * 2) :]
                if context_strategy == "sliding_window"
                else messages
            )

            payload = {
                "model": model,
                "messages": context,
                "stream": False,
                "options": {
                    "num_predict": max_tokens,
                    "temperature": 0.0,
                    "seed": 42,
                },
            }

            result = RequestResult()
            result.request_id = turn_idx
            t0 = time.perf_counter()

            try:
                resp = await client.post(
                    f"{url}/api/chat",
                    json=payload,
                    timeout=timeout,
                )
                result.wall_ms = (time.perf_counter() - t0) * 1000.0
                resp.raise_for_status()
                data = resp.json()

                timing = _extract_ollama_timing(data)
                result.prompt_tokens = timing["prompt_tokens"]
                result.completion_tokens = timing["completion_tokens"]
                result.prompt_eval_ms = timing["prompt_eval_ms"]
                result.eval_ms = timing["eval_ms"]
                result.total_duration_ms = timing["total_duration_ms"]
                result.load_duration_ms = timing["load_duration_ms"]
                result.response_text = data.get("message", {}).get("content", "")

                if result.eval_ms > 0 and result.completion_tokens > 0:
                    result.tokens_per_s = result.completion_tokens / (
                        result.eval_ms / 1000.0
                    )

                messages.append(
                    {
                        "role": "assistant",
                        "content": result.response_text,
                    }
                )
                consecutive_errors = 0

            except httpx.TimeoutException:
                result.wall_ms = (time.perf_counter() - t0) * 1000.0
                result.status = "timeout"
                messages.append({"role": "assistant", "content": ""})
                consecutive_errors += 1
            except Exception as exc:
                result.wall_ms = (time.perf_counter() - t0) * 1000.0
                result.status = f"error: {exc}"
                messages.append({"role": "assistant", "content": ""})
                consecutive_errors += 1
                log.warning("Chat turn %d failed: %s", turn_idx, exc)

            results.append(result)

            if consecutive_errors >= 3:
                log.error("Aborting conversation after 3 consecutive errors")
                break

    return results
