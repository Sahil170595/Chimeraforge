"""vLLM backend adapter.

Implements the Backend interface against the vLLM OpenAI-compatible API,
streamed with ``stream_options.include_usage`` so decode is timed separately
from prefill (read from vLLM source at v0.30.0: the usage block arrives in a
final chunk with empty ``choices``, before ``data: [DONE]``).
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

import httpx

from chimeraforge.bench.backends._streaming import stream_openai_completion
from chimeraforge.bench.backends.base import Backend, fetch_json_field, identity_message
from chimeraforge.bench.metrics import RunMetrics

logger = logging.getLogger(__name__)


class VLLMBackend(Backend):
    """vLLM serving backend (OpenAI-compatible, http://localhost:8000 by default)."""

    name = "vllm"

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
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
        """GET /health, then GET /version: running means vLLM named itself.

        /health returns an empty 200 (vLLM v0.30.0 source), which any web app on
        :8000 can also return -- on the dev box a generic uvicorn app did, and
        this reported "vLLM is running". /version returns {"version": ...}.
        """
        try:
            client = await self._get_client()
            resp = await client.get(f"{self.base_url}/health", timeout=10)
            if resp.status_code != 200:
                return False, f"vLLM returned status {resp.status_code}"
            version = await self.get_version()
            if not version:
                return False, identity_message(
                    "vLLM", self.base_url, "GET /version returned no version"
                )
            return True, f"vLLM {version} is running"
        except httpx.ConnectError:
            return False, f"vLLM not running at {self.base_url}"
        except httpx.TimeoutException:
            return False, f"vLLM timed out at {self.base_url}"

    async def check_model(self, model: str) -> tuple[bool, str]:
        """GET /v1/models and check if model is listed."""
        try:
            client = await self._get_client()
            resp = await client.get(f"{self.base_url}/v1/models", timeout=30)
            if resp.status_code != 200:
                return False, f"Cannot list models (status {resp.status_code})"
            try:
                data = resp.json()
            except ValueError:
                logger.debug("vLLM model-list response is not JSON")
                return False, "vLLM model-list response is malformed"
            rows = data.get("data") if isinstance(data, dict) else None
            if not isinstance(rows, list) or any(
                not isinstance(row, dict)
                or not isinstance(row.get("id"), str)
                or not row["id"].strip()
                for row in rows
            ):
                return False, "vLLM model-list response is malformed"
            model_ids = [row["id"] for row in rows]
            if model in model_ids:
                return True, ""
            return False, (
                f"Model '{model}' not found. Available: {', '.join(model_ids) or 'none'}"
            )
        except httpx.ConnectError:
            return False, f"vLLM not running at {self.base_url}"
        except httpx.TimeoutException:
            return False, f"vLLM timed out at {self.base_url}"
        except httpx.HTTPError as exc:
            return False, f"vLLM model check failed at {self.base_url}: {exc}"

    async def generate(
        self,
        model: str,
        prompt: str,
        options: dict | None = None,
    ) -> RunMetrics:
        """Stream POST /v1/completions; decode = (tokens - 1) / first-to-last token.

        This reported completion tokens over wall clock -- prefill included -- as
        the decode rate that `measure` files into the corpus.

        Raises:
            httpx.HTTPStatusError: The server rejected the request.
            RuntimeError: No usage block, or too few tokens to time a decode.
        """
        opts = options or {}
        payload = {
            "model": model,
            "prompt": prompt,
            "max_tokens": opts.get("max_tokens", 256),
            "temperature": opts.get("temperature", 0.7),
        }
        client = await self._get_client()
        return await stream_openai_completion(
            client, f"{self.base_url}/v1/completions", payload, self._clock, "vLLM", 300
        )

    async def get_version(self) -> str | None:
        """GET /version -> ``{"version": ...}`` (vLLM v0.30.0 source), else None."""
        client = await self._get_client()
        return await fetch_json_field(client, f"{self.base_url}/version", "version")

    async def observe_serving(self, model: str) -> dict:
        from chimeraforge.bench.serving import observe_vllm

        return await observe_vllm(await self._get_client(), self.base_url, model)
