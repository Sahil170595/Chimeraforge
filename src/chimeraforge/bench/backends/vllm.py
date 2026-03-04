"""vLLM backend adapter.

Implements the Backend interface against the vLLM OpenAI-compatible API.
vLLM exposes /v1/completions with usage stats in the response.
"""

from __future__ import annotations

import time

import httpx

from chimeraforge.bench.backends.base import Backend
from chimeraforge.bench.metrics import RunMetrics


class VLLMBackend(Backend):
    """vLLM serving backend (OpenAI-compatible, http://localhost:8000 by default)."""

    name = "vllm"

    def __init__(self, base_url: str = "http://localhost:8000") -> None:
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
        """GET /health or /v1/models to check availability."""
        try:
            client = await self._get_client()
            resp = await client.get(f"{self.base_url}/health", timeout=10)
            if resp.status_code == 200:
                return True, "vLLM is running"
            # Fallback: try /v1/models
            resp = await client.get(f"{self.base_url}/v1/models", timeout=10)
            if resp.status_code == 200:
                return True, "vLLM is running"
            return False, f"vLLM returned status {resp.status_code}"
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
            data = resp.json()
            model_ids = [m["id"] for m in data.get("data", [])]
            if model in model_ids:
                return True, ""
            return False, (
                f"Model '{model}' not found. Available: {', '.join(model_ids) or 'none'}"
            )
        except httpx.ConnectError:
            return False, f"vLLM not running at {self.base_url}"

    async def generate(
        self,
        model: str,
        prompt: str,
        options: dict | None = None,
    ) -> RunMetrics:
        """POST /v1/completions, extract usage and timing."""
        opts = options or {}
        payload = {
            "model": model,
            "prompt": prompt,
            "max_tokens": opts.get("max_tokens", 256),
            "temperature": opts.get("temperature", 0.7),
        }

        client = await self._get_client()
        t0 = time.perf_counter()
        resp = await client.post(
            f"{self.base_url}/v1/completions",
            json=payload,
            timeout=300,
        )
        total_s = time.perf_counter() - t0
        resp.raise_for_status()
        data = resp.json()

        usage = data.get("usage", {})
        completion_tokens = usage.get("completion_tokens", 0)
        total_duration_ms = total_s * 1000

        # vLLM non-streaming API doesn't expose TTFT; throughput from wall clock
        eval_duration_ms = total_duration_ms
        throughput = completion_tokens / total_s if total_s > 0 else 0.0

        return RunMetrics(
            tokens_generated=completion_tokens,
            throughput_tps=throughput,
            ttft_ms=-1.0,  # Not measurable without streaming
            total_duration_ms=total_duration_ms,
            prompt_eval_duration_ms=0.0,
            eval_duration_ms=eval_duration_ms,
        )

    async def get_version(self) -> str | None:
        """GET /version or extract from /v1/models metadata."""
        try:
            client = await self._get_client()
            resp = await client.get(f"{self.base_url}/version", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("version", str(data))
        except Exception:
            pass
        return None
