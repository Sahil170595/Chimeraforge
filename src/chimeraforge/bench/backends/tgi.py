"""TGI (Text Generation Inference) backend adapter.

Implements the Backend interface against the HuggingFace TGI HTTP API.
TGI exposes /generate with detailed timing in the response.
"""

from __future__ import annotations

import time

import httpx

from chimeraforge.bench.backends.base import Backend
from chimeraforge.bench.metrics import RunMetrics


class TGIBackend(Backend):
    """HuggingFace TGI serving backend (http://localhost:8080 by default)."""

    name = "tgi"

    def __init__(self, base_url: str = "http://localhost:8080") -> None:
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

    async def generate(
        self,
        model: str,
        prompt: str,
        options: dict | None = None,
    ) -> RunMetrics:
        """POST /generate, extract timing from details."""
        opts = options or {}
        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": opts.get("max_new_tokens", 256),
                "temperature": opts.get("temperature", 0.7),
            },
        }

        client = await self._get_client()
        t0 = time.perf_counter()
        resp = await client.post(
            f"{self.base_url}/generate",
            json=payload,
            timeout=300,
        )
        total_s = time.perf_counter() - t0
        resp.raise_for_status()
        data = resp.json()

        # TGI response structure
        details = data.get("details", {})
        generated_tokens = details.get("generated_tokens", 0)
        total_duration_ms = total_s * 1000

        # TGI timing fields vary by version; try multiple known field names
        prefill_time = (
            details.get("prefill_time")  # TGI 2.x (seconds)
            or details.get("prefill_duration_ns", 0) / 1e9  # hypothetical ns
        )
        decode_time = (
            details.get("decode_time")  # TGI 2.x (seconds)
            or details.get("decode_duration_ns", 0) / 1e9
        )

        if prefill_time and prefill_time > 0:
            prompt_eval_duration_ms = prefill_time * 1000
            eval_duration_ms = decode_time * 1000 if decode_time else total_duration_ms
        else:
            # Timing not available from TGI response
            prompt_eval_duration_ms = 0.0
            eval_duration_ms = total_duration_ms

        throughput = generated_tokens / total_s if total_s > 0 else 0.0
        ttft = prompt_eval_duration_ms if prompt_eval_duration_ms > 0 else -1.0

        return RunMetrics(
            tokens_generated=generated_tokens,
            throughput_tps=throughput,
            ttft_ms=ttft,
            total_duration_ms=total_duration_ms,
            prompt_eval_duration_ms=prompt_eval_duration_ms,
            eval_duration_ms=eval_duration_ms,
        )

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
