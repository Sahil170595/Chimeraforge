"""Ollama backend adapter.

Implements the Backend interface against the Ollama REST API.
Uses stream=False to extract eval_count / eval_duration / prompt_eval_duration
from the final JSON response, matching the banterhearts measurement pattern.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
import json
import math
from typing import Callable

import httpx

from chimeraforge.bench.backends.base import (
    Backend,
    GenerationObservation,
    fetch_json_field,
    identity_message,
)
from chimeraforge.bench.metrics import RunMetrics

# What Ollama's root route returns (server/routes.go, v0.34.4): its self-identification.
OLLAMA_BANNER = "Ollama is running"
MAX_STREAM_BYTES = 16 * 1024 * 1024
# Bound synchronous frame work between cancellation/deadline checkpoints.
STREAM_FRAME_BATCH = 32
STREAM_CHUNK_BATCH = 32
STREAM_BYTE_BATCH = 64 * 1024


def _native_number(data: dict, name: str, *, count: bool = False) -> int | float | None:
    value = data.get(name)
    try:
        if (
            type(value) not in ((int,) if count else (int, float))
            or not math.isfinite(value)
            or value < 0
        ):
            return None
    except OverflowError:
        return None
    return value if count else value / 1e6


async def _json_lines(response: httpx.Response) -> AsyncIterator[dict]:
    """Bound native NDJSON bytes without retaining prompt or completion content."""
    total, frames = 0, 0
    chunks, buffered_work = 0, 0
    fragments = []
    # A fixed chunk_size coalesces small frames until EOF and loses first-output timing.
    async for chunk in response.aiter_bytes():
        total += len(chunk)
        if total > MAX_STREAM_BYTES:
            raise RuntimeError("Ollama stream exceeds the trace response limit")
        chunks += 1
        buffered_work += len(chunk)
        if chunks >= STREAM_CHUNK_BATCH or buffered_work >= STREAM_BYTE_BATCH:
            chunks, buffered_work = 0, 0
            await asyncio.sleep(0)
        offset = 0
        while (end := chunk.find(b"\n", offset)) >= 0:
            fragments.append(chunk[offset:end])
            line = b"".join(fragments)
            fragments.clear()
            offset = end + 1
            if line.strip():
                yield json.loads(line)
            frames += 1
            if frames == STREAM_FRAME_BATCH:
                frames = 0
                await asyncio.sleep(0)
        fragments.append(chunk[offset:])
    final = b"".join(fragments)
    if final.strip():
        await asyncio.sleep(0)
        yield json.loads(final)


class OllamaBackend(Backend):
    """Ollama serving backend (http://localhost:11434 by default)."""

    name = "ollama"

    def __init__(self, base_url: str = "http://localhost:11434") -> None:
        self.base_url = base_url.rstrip("/")
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=300)
        return self._client

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def health_check(self) -> tuple[bool, str]:
        """GET / -- Ollama answers with the literal banner "Ollama is running".

        A 200 alone is not Ollama: any web server on the port returns one. The
        banner is the identity check, so an impostor is refused before a
        benchmark is filed against the wrong engine.
        """
        try:
            client = await self._get_client()
            resp = await client.get(f"{self.base_url}/", timeout=10)
            if resp.status_code != 200:
                return False, f"Ollama returned status {resp.status_code}"
            if OLLAMA_BANNER not in resp.text:
                return False, identity_message(
                    "Ollama", self.base_url, f"no {OLLAMA_BANNER!r} banner at GET /"
                )
            return True, "Ollama is running"
        except httpx.ConnectError:
            return False, f"Ollama not running at {self.base_url}"
        except httpx.TimeoutException:
            return False, f"Ollama timed out at {self.base_url}"

    async def check_model(self, model: str) -> tuple[bool, str]:
        """POST /api/show to verify model availability."""
        try:
            client = await self._get_client()
            resp = await client.post(
                f"{self.base_url}/api/show",
                json={"name": model},
                timeout=30,
            )
            if resp.status_code == 200:
                return True, ""
            return False, f"Model not found. Run: ollama pull {model}"
        except httpx.ConnectError:
            return False, f"Ollama not running at {self.base_url}"
        except httpx.TimeoutException:
            return False, f"Ollama timed out at {self.base_url}"
        except httpx.HTTPError as exc:
            return False, f"Ollama model check failed at {self.base_url}: {exc}"

    async def generate(
        self,
        model: str,
        prompt: str,
        options: dict | None = None,
    ) -> RunMetrics:
        """POST /api/generate with stream=False, extract timing metrics."""
        payload: dict = {
            "model": model,
            "prompt": prompt,
            "stream": False,
        }
        if options:
            payload["options"] = options

        client = await self._get_client()
        resp = await client.post(
            f"{self.base_url}/api/generate",
            json=payload,
            timeout=300,
        )
        resp.raise_for_status()
        data = resp.json()

        eval_count = data.get("eval_count", 0)
        eval_duration_ns = data.get("eval_duration", 0)
        prompt_eval_duration_ns = data.get("prompt_eval_duration", 0)
        total_duration_ns = data.get("total_duration", 0)

        eval_duration_ms = eval_duration_ns / 1e6
        prompt_eval_duration_ms = prompt_eval_duration_ns / 1e6
        total_duration_ms = total_duration_ns / 1e6

        throughput = eval_count / (eval_duration_ns / 1e9) if eval_duration_ns > 0 else 0.0
        ttft = prompt_eval_duration_ms

        return RunMetrics(
            tokens_generated=eval_count,
            throughput_tps=throughput,
            ttft_ms=ttft,
            total_duration_ms=total_duration_ms,
            prompt_eval_duration_ms=prompt_eval_duration_ms,
            eval_duration_ms=eval_duration_ms,
            prompt_tokens=data.get("prompt_eval_count"),
            cached_prompt_tokens=data.get("prompt_eval_cached_count"),
            ttft_basis="server-prefill-duration",
        )

    async def generate_text(
        self,
        model: str,
        prompt: str,
        options: dict | None = None,
    ) -> str:
        """POST /api/generate (stream=False) and return the response text."""
        payload: dict = {"model": model, "prompt": prompt, "stream": False}
        if options:
            payload["options"] = options

        client = await self._get_client()
        resp = await client.post(
            f"{self.base_url}/api/generate",
            json=payload,
            timeout=300,
        )
        resp.raise_for_status()
        return resp.json().get("response", "")

    async def generate_observed(
        self,
        model: str,
        prompt: str,
        options: dict,
        on_first_output: Callable[[], None],
    ) -> GenerationObservation:
        """Stream real output arrivals; final native prefill remains a separate basis."""
        client = await self._get_client()
        final = None
        seen_output = False
        async with client.stream(
            "POST",
            f"{self.base_url}/api/generate",
            json={"model": model, "prompt": prompt, "stream": True, "options": options},
            timeout=300,
        ) as response:
            response.raise_for_status()
            async for data in _json_lines(response):
                if type(data) is not dict or "error" in data:
                    raise RuntimeError("Ollama returned an invalid generation frame")
                content = data.get("response")
                if content is not None and type(content) is not str:
                    raise RuntimeError("Ollama returned invalid output metadata")
                if content and not seen_output:
                    on_first_output()
                    seen_output = True
                if data.get("done") is True:
                    final = data
                    break
        if final is None:
            raise RuntimeError("Ollama stream ended without a completed response")
        tokens = _native_number(final, "eval_count", count=True)
        decode = _native_number(final, "eval_duration")
        prefill = _native_number(final, "prompt_eval_duration")
        tpot = decode / tokens if decode is not None and tokens is not None and tokens > 0 else None
        return GenerationObservation(
            {
                "tokens_generated": tokens,
                "prompt_tokens": _native_number(final, "prompt_eval_count", count=True),
                "cached_prompt_tokens": _native_number(
                    final, "prompt_eval_cached_count", count=True
                ),
                "throughput_tps": 1000 / tpot if tpot is not None and tpot > 0 else None,
                "ttft_ms": prefill,
                "ttft_basis": "server-prefill-duration",
                "total_duration_ms": _native_number(final, "total_duration"),
                "prompt_eval_duration_ms": prefill,
                "eval_duration_ms": decode,
            },
            tpot,
            "server-decode-duration/output-token-count",
        )

    async def get_version(self) -> str | None:
        """GET /api/version -> ``{"version": ...}``, else None."""
        client = await self._get_client()
        return await fetch_json_field(client, f"{self.base_url}/api/version", "version")

    async def observe_serving(self, model: str) -> dict:
        from chimeraforge.bench.serving import observe_ollama

        return await observe_ollama(await self._get_client(), self.base_url, model)
