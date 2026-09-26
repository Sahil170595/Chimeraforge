"""SGLang backend adapter.

Implements the Backend interface against SGLang's OpenAI-compatible
``/v1/completions`` endpoint, streamed, so the decode rate can be separated from
prefill. The planner predicts a single-stream DECODE rate; completion tokens over
wall clock (what a non-streaming adapter can report) folds prefill into that
number and under-reports it by an amount that grows with prompt length.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable

import httpx

from chimeraforge.bench.backends.base import Backend
from chimeraforge.bench.metrics import RunMetrics

logger = logging.getLogger(__name__)

# Endpoint names, the default port and the streamed usage chunk were read from
# SGLang source at v0.5.20 (arg_groups/fields/serving.py, entrypoints/).
# `python -m sglang.launch_server` listens on 30000 unless --port is given.
DEFAULT_SGLANG_URL = "http://localhost:30000"
DEFAULT_MAX_TOKENS = 256
DEFAULT_TEMPERATURE = 0.7
REQUEST_TIMEOUT_S = 300
PROBE_TIMEOUT_S = 10
MODEL_LIST_TIMEOUT_S = 30

# Endpoints that report the server version, newest name first. SGLang renamed
# /get_server_info to /server_info; older servers only answer the former.
VERSION_ENDPOINTS = ("/server_info", "/get_server_info")

_SSE_PREFIX = "data:"
_SSE_DONE = "[DONE]"


class SGLangBackend(Backend):
    """SGLang serving backend (OpenAI-compatible, http://localhost:30000 by default)."""

    name = "sglang"

    def __init__(
        self,
        base_url: str = DEFAULT_SGLANG_URL,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._transport = transport
        self._clock = clock or time.perf_counter
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=REQUEST_TIMEOUT_S, transport=self._transport)
        return self._client

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def health_check(self) -> tuple[bool, str]:
        """GET /health; 200 means the server is up and its scheduler is responsive."""
        try:
            client = await self._get_client()
            resp = await client.get(f"{self.base_url}/health", timeout=PROBE_TIMEOUT_S)
            if resp.status_code == 200:
                return True, "SGLang is running"
            return False, f"SGLang returned status {resp.status_code}"
        except httpx.ConnectError:
            return False, f"SGLang not running at {self.base_url}"
        except httpx.TimeoutException:
            return False, f"SGLang timed out at {self.base_url}"

    async def check_model(self, model: str) -> tuple[bool, str]:
        """GET /v1/models and check that *model* is the served id."""
        try:
            client = await self._get_client()
            resp = await client.get(f"{self.base_url}/v1/models", timeout=MODEL_LIST_TIMEOUT_S)
            if resp.status_code != 200:
                return False, f"Cannot list models (status {resp.status_code})"
            model_ids = [m["id"] for m in resp.json().get("data", [])]
            if model in model_ids:
                return True, ""
            return False, (
                f"Model '{model}' not found. SGLang is serving: "
                f"{', '.join(model_ids) or 'none'} (pass that id, or relaunch with "
                "--served-model-name)"
            )
        except httpx.ConnectError:
            return False, f"SGLang not running at {self.base_url}"
        except httpx.TimeoutException:
            return False, f"SGLang timed out at {self.base_url}"
        except httpx.HTTPError as exc:
            return False, f"SGLang model check failed at {self.base_url}: {exc}"

    async def generate(
        self,
        model: str,
        prompt: str,
        options: dict | None = None,
    ) -> RunMetrics:
        """Stream POST /v1/completions; time first and last token client-side.

        Token count comes from the server's ``usage`` block, never from counting
        chunks -- one chunk can carry several tokens. A response without usage
        is a failed run: there is no honest way to recover the count.

        Raises:
            httpx.HTTPStatusError: The server rejected the request.
            RuntimeError: No usage block, or too few tokens to time a decode.
        """
        opts = options or {}
        payload = {
            "model": model,
            "prompt": prompt,
            "max_tokens": opts.get("max_tokens", DEFAULT_MAX_TOKENS),
            "temperature": opts.get("temperature", DEFAULT_TEMPERATURE),
            "stream": True,
            "stream_options": {"include_usage": True},
        }

        client = await self._get_client()
        t0 = self._clock()
        t_first: float | None = None
        t_last: float | None = None
        usage: dict | None = None
        async with client.stream(
            "POST", f"{self.base_url}/v1/completions", json=payload, timeout=REQUEST_TIMEOUT_S
        ) as resp:
            if resp.status_code >= 400:
                await resp.aread()
                resp.raise_for_status()
            async for line in resp.aiter_lines():
                chunk = _parse_sse(line)
                if chunk is None:
                    continue
                if chunk.get("usage"):
                    usage = chunk["usage"]
                if any(c.get("text") for c in chunk.get("choices") or []):
                    now = self._clock()
                    if t_first is None:
                        t_first = now
                    t_last = now
        t_end = self._clock()

        if not usage or "completion_tokens" not in usage:
            raise RuntimeError(
                "SGLang returned no usage block, so the generated token count is "
                "unknown; the run is discarded rather than estimated"
            )
        tokens = int(usage["completion_tokens"])
        if tokens < 2 or t_first is None or t_last is None or t_last <= t_first:
            raise RuntimeError(
                f"{tokens} token(s) streamed: a decode rate needs at least two tokens "
                "arriving at distinct times. Raise max_tokens."
            )

        ttft_ms = (t_first - t0) * 1000
        decode_s = t_last - t_first
        return RunMetrics(
            tokens_generated=tokens,
            # The first token is produced by prefill; the remaining tokens - 1
            # arrive over the decode interval.
            throughput_tps=(tokens - 1) / decode_s,
            ttft_ms=ttft_ms,
            total_duration_ms=(t_end - t0) * 1000,
            prompt_eval_duration_ms=ttft_ms,
            eval_duration_ms=decode_s * 1000,
        )

    async def get_version(self) -> str | None:
        """Read the version from the server-info endpoint, trying both names."""
        client = await self._get_client()
        for path in VERSION_ENDPOINTS:
            try:
                resp = await client.get(f"{self.base_url}{path}", timeout=PROBE_TIMEOUT_S)
            except httpx.HTTPError as exc:
                logger.debug("SGLang version probe %s failed: %s", path, exc)
                continue
            if resp.status_code == 200:
                version = resp.json().get("version")
                if version:
                    return str(version)
        return None


def _parse_sse(line: str) -> dict | None:
    """One SSE ``data:`` line -> its JSON payload; None for keep-alives and [DONE]."""
    line = line.strip()
    if not line.startswith(_SSE_PREFIX):
        return None
    data = line[len(_SSE_PREFIX) :].strip()
    if not data or data == _SSE_DONE:
        return None
    try:
        return json.loads(data)
    except json.JSONDecodeError:
        logger.warning("SGLang sent an unparseable stream line: %.120s", data)
        return None
