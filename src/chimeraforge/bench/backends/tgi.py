"""TGI (Text Generation Inference) backend adapter.

Implements the Backend interface against the HuggingFace TGI HTTP API,
streaming ``/generate_stream`` so decode is timed separately from prefill.
Read from TGI source at v3.3.7: each event is a ``StreamResponse`` with a
``token`` (``text``, ``special``); the final event carries
``details.generated_tokens``; the stream simply ends (no ``[DONE]``).
"""

from __future__ import annotations

import time
from collections.abc import Callable

import httpx

from chimeraforge.bench.backends._streaming import StreamTiming, decode_metrics, parse_sse
from chimeraforge.bench.backends.base import Backend
from chimeraforge.bench.metrics import RunMetrics


class TGIBackend(Backend):
    """HuggingFace TGI serving backend (http://localhost:8080 by default)."""

    name = "tgi"

    def __init__(
        self,
        base_url: str = "http://localhost:8080",
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
            self._client = httpx.AsyncClient(timeout=300, transport=self._transport)
        return self._client

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def health_check(self) -> tuple[bool, str]:
        """GET /health to check TGI availability."""
        try:
            client = await self._get_client()
            resp = await client.get(f"{self.base_url}/health", timeout=10)
            if resp.status_code == 200:
                return True, "TGI is running"
            return False, f"TGI returned status {resp.status_code}"
        except httpx.ConnectError:
            return False, f"TGI not running at {self.base_url}"
        except httpx.TimeoutException:
            return False, f"TGI timed out at {self.base_url}"

    async def check_model(self, model: str) -> tuple[bool, str]:
        """GET /info to verify model is loaded.

        TGI loads a single model at startup, so we verify the loaded
        model_id matches exactly or that the model name appears as a
        path component of the loaded model_id (e.g. "llama-3b" matches
        "meta-llama/Llama-3.2-3B-Instruct").
        """
        try:
            client = await self._get_client()
            resp = await client.get(f"{self.base_url}/info", timeout=30)
            if resp.status_code != 200:
                return False, f"Cannot get model info (status {resp.status_code})"
            data = resp.json()
            loaded = data.get("model_id", "")
            # Exact match or model is a path component of loaded model_id
            if model == loaded:
                return True, ""
            # Check if model name appears after a "/" in the loaded ID
            loaded_parts = loaded.lower().split("/")
            if model.lower() in loaded_parts:
                return True, ""
            return False, (
                f"TGI has '{loaded}' loaded, not '{model}'. Restart TGI with the desired model."
            )
        except httpx.ConnectError:
            return False, f"TGI not running at {self.base_url}"
        except httpx.TimeoutException:
            return False, f"TGI timed out at {self.base_url}"
        except httpx.HTTPError as exc:
            return False, f"TGI model check failed at {self.base_url}: {exc}"

    async def generate(
        self,
        model: str,
        prompt: str,
        options: dict | None = None,
    ) -> RunMetrics:
        """Stream POST /generate_stream; decode = (tokens - 1) / first-to-last token.

        This read ``details.decode_time`` from a non-streamed /generate when TGI
        sent it, and otherwise divided tokens by wall clock -- prefill included --
        while filing the result as a decode rate. Special tokens do not count as
        content arrivals; the token count is the server-reported generated_tokens.

        Raises:
            httpx.HTTPStatusError: The server rejected the request.
            RuntimeError: No final details, or too few tokens to time a decode.
        """
        opts = options or {}
        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": opts.get("max_new_tokens", opts.get("max_tokens", 256)),
                "temperature": opts.get("temperature", 0.7),
                "details": True,
            },
        }
        client = await self._get_client()
        timing = StreamTiming(t0=self._clock())
        async with client.stream(
            "POST", f"{self.base_url}/generate_stream", json=payload, timeout=300
        ) as resp:
            if resp.status_code >= 400:
                await resp.aread()
                resp.raise_for_status()
            async for line in resp.aiter_lines():
                event = parse_sse(line, "TGI")
                if event is None:
                    continue
                token = event.get("token") or {}
                if token.get("text") and not token.get("special"):
                    timing.mark_token(self._clock())
                details = event.get("details") or {}
                if details.get("generated_tokens") is not None:
                    timing.tokens = details["generated_tokens"]
        timing.t_end = self._clock()
        return decode_metrics(timing, "TGI", "final details (generated_tokens)")

    async def get_version(self) -> str | None:
        """GET /info and extract version."""
        try:
            client = await self._get_client()
            resp = await client.get(f"{self.base_url}/info", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("version")
        except Exception:
            pass
        return None
