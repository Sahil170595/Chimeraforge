"""Ollama backend adapter.

Implements the Backend interface against the Ollama REST API.
Uses stream=False to extract eval_count / eval_duration / prompt_eval_duration
from the final JSON response, matching the banterhearts measurement pattern.
"""

from __future__ import annotations

import httpx

from chimeraforge.bench.backends.base import Backend
from chimeraforge.bench.metrics import RunMetrics


class OllamaBackend(Backend):
    """Ollama serving backend (http://localhost:11434 by default)."""

    name = "ollama"

    def __init__(self, base_url: str = "http://localhost:11434") -> None:
        self.base_url = base_url.rstrip("/")

    async def health_check(self) -> tuple[bool, str]:
        """GET / -- Ollama returns 'Ollama is running'."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{self.base_url}/", timeout=10)
                if resp.status_code == 200:
                    return True, "Ollama is running"
                return False, f"Ollama returned status {resp.status_code}"
        except httpx.ConnectError:
            return False, f"Ollama not running at {self.base_url}"
        except httpx.TimeoutException:
            return False, f"Ollama timed out at {self.base_url}"

    async def check_model(self, model: str) -> tuple[bool, str]:
        """POST /api/show to verify model availability."""
        try:
            async with httpx.AsyncClient() as client:
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

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=300,
            )
            resp.raise_for_status()
            data = resp.json()

        eval_count = data.get("eval_count", 0)
        eval_duration_ns = data.get("eval_duration", 1)
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
        )

    async def get_version(self) -> str | None:
        """GET /api/version."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{self.base_url}/api/version", timeout=10)
                if resp.status_code == 200:
                    return resp.json().get("version")
        except Exception:
            pass
        return None
