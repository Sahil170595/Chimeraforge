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

    async def health_check(self) -> tuple[bool, str]:
        """GET /health to check TGI availability."""
        try:
            async with httpx.AsyncClient() as client:
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

        TGI loads a single model at startup, so we just verify the
        loaded model name matches.
        """
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{self.base_url}/info", timeout=30)
                if resp.status_code != 200:
                    return False, f"Cannot get model info (status {resp.status_code})"
                data = resp.json()
                loaded = data.get("model_id", "")
                if model in loaded or loaded in model:
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

        async with httpx.AsyncClient() as client:
            t0 = time.perf_counter()
            resp = await client.post(
                f"{self.base_url}/generate",
                json=payload,
                timeout=300,
            )
            total_s = time.perf_counter() - t0
            resp.raise_for_status()
            data = resp.json()

        # TGI returns details with generated_tokens and optional timings
        details = data.get("details", {})
        generated_tokens = details.get("generated_tokens", 0)
        total_duration_ms = total_s * 1000

        # TGI prefill/decode timing (nanoseconds in some versions, ms in others)
        prefill_ns = details.get("prefill_duration_ns", 0)
        decode_ns = details.get("decode_duration_ns", 0)

        if prefill_ns > 0:
            prompt_eval_duration_ms = prefill_ns / 1e6
            eval_duration_ms = decode_ns / 1e6
        else:
            prompt_eval_duration_ms = 0.0
            eval_duration_ms = total_duration_ms

        throughput = generated_tokens / total_s if total_s > 0 else 0.0

        return RunMetrics(
            tokens_generated=generated_tokens,
            throughput_tps=throughput,
            ttft_ms=prompt_eval_duration_ms,
            total_duration_ms=total_duration_ms,
            prompt_eval_duration_ms=prompt_eval_duration_ms,
            eval_duration_ms=eval_duration_ms,
        )

    async def get_version(self) -> str | None:
        """GET /info and extract version."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{self.base_url}/info", timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("version")
        except Exception:
            pass
        return None
