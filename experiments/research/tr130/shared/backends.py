"""Serving backend abstraction for TR130.

Provides a ServingBackend ABC with three implementations:
- OllamaBackend: Native Windows process, /api/generate
- VllmBackend: Docker container, /v1/completions (OpenAI-compatible)
- TgiBackend: Docker container, /generate with details=true
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
from dataclasses import dataclass, field
import json
import logging
import os
from pathlib import Path
import shutil
import subprocess
import time

import httpx

from research.tr130.shared.docker_utils import (
    docker_logs,
    docker_run,
    ensure_container_stopped,
)

log = logging.getLogger("tr130.backends")


# ── Result data classes ───────────────────────────────────────────────


@dataclass
class BackendRequestResult:
    """Unified result from any backend's generate() call."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    wall_ms: float = 0.0
    prefill_ms: float | None = None  # Ollama + TGI only
    decode_ms: float | None = None  # Ollama + TGI only
    effective_tps: float = 0.0  # Universal: completion_tokens / wall_ms * 1000
    gpu_tokens_per_s: float | None = (
        None  # Ollama: completion_tokens / decode_ms * 1000
    )
    response_text: str = ""
    status: str = "ok"
    backend_metadata: dict = field(default_factory=dict)


@dataclass
class BackendStreamResult(BackendRequestResult):
    """Extends with streaming-specific fields."""

    ttft_ms: float | None = None


# ── Abstract base ────────────────────────────────────────────────────


class ServingBackend(ABC):
    """Abstract serving backend: wraps process/container lifecycle + HTTP API."""

    name: str
    port: int
    quantization: str
    _current_model: str | None

    @abstractmethod
    def start(
        self, model_hf_id: str, model_ollama_tag: str | None = None, **kwargs
    ) -> None:
        """Start the backend and load a model."""

    @abstractmethod
    def stop(self) -> None:
        """Stop the backend."""

    @abstractmethod
    def is_ready(self) -> bool:
        """Check if the backend is healthy and ready to serve."""

    def wait_ready(self, timeout_s: float = 180, poll_s: float = 3.0) -> bool:
        """Poll is_ready() every poll_s seconds up to timeout_s."""
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            if self.is_ready():
                return True
            time.sleep(poll_s)
        return False

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        max_tokens: int = 128,
        temperature: float = 0.0,
        seed: int = 42,
    ) -> BackendRequestResult:
        """Send a single non-streaming generate request."""

    @abstractmethod
    async def generate_stream(
        self,
        prompt: str,
        max_tokens: int = 128,
        temperature: float = 0.0,
        seed: int = 42,
    ) -> BackendStreamResult:
        """Send a streaming request, measuring TTFT."""

    def warmup(self, prompt: str = "Hello", n: int = 3, max_tokens: int = 16) -> dict:
        """Send n warmup requests. Returns summary."""
        results = []
        for i in range(n):
            r = asyncio.run(self.generate(prompt, max_tokens=max_tokens))
            results.append(r)
            log.debug(
                "Warmup %d/%d: %.1f ms, %d tok",
                i + 1,
                n,
                r.wall_ms,
                r.completion_tokens,
            )
        ok = sum(1 for r in results if r.status == "ok")
        return {
            "warmup_requests": n,
            "warmup_ok": ok,
            "backend": self.name,
            "model": self._current_model,
        }

    @property
    def base_url(self) -> str:
        return f"http://localhost:{self.port}"


# ── Ollama ───────────────────────────────────────────────────────────


class OllamaBackend(ServingBackend):
    """Ollama native backend (Windows process, /api/generate)."""

    name = "ollama"
    quantization = "Q4_0"

    def __init__(self, cfg: dict):
        self.port = cfg.get("port", 11434)
        self._timeout_s = cfg.get("timeout_s", 120)
        self._proc: subprocess.Popen | None = None
        self._we_started: bool = False
        self._current_model: str | None = None

    def start(
        self, model_hf_id: str, model_ollama_tag: str | None = None, **kwargs
    ) -> None:
        tag = model_ollama_tag or model_hf_id
        self._current_model = tag

        # Check if Ollama is already running
        if self.is_ready():
            log.info("Ollama already running on port %d", self.port)
            self._we_started = False
        else:
            ollama_bin = shutil.which("ollama")
            if ollama_bin is None:
                raise RuntimeError("ollama not found in PATH")
            env = os.environ.copy()
            env["OLLAMA_HOST"] = f"0.0.0.0:{self.port}"
            self._proc = subprocess.Popen(
                [ollama_bin, "serve"],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self._we_started = True
            log.info("Started Ollama serve (pid=%d)", self._proc.pid)
            if not self.wait_ready(timeout_s=30):
                raise RuntimeError("Ollama failed to start within 30s")

        # Pre-load model by making a tiny request (not a full warmup —
        # phase runners call warmup() separately)
        log.info("Pre-loading model %s in Ollama", tag)
        try:
            r = asyncio.run(self.generate("test", max_tokens=1))
            log.info("Model %s loaded (status=%s)", tag, r.status)
        except Exception as e:
            log.warning("Model pre-load failed: %s", e)

    def stop(self) -> None:
        if self._proc is not None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._proc.kill()
            self._proc = None
            self._we_started = False
            log.info("Ollama stopped (process terminated)")
        elif self._we_started:
            # We started it but lost the proc handle — should not happen
            log.warning("Ollama: _we_started=True but no proc handle")
            self._we_started = False
        else:
            # We didn't start Ollama — unload the model to free VRAM
            # but leave the server running
            if self._current_model:
                try:
                    import urllib.request

                    data = json.dumps(
                        {
                            "model": self._current_model,
                            "keep_alive": 0,
                        }
                    ).encode()
                    req = urllib.request.Request(
                        f"{self.base_url}/api/generate",
                        data=data,
                        headers={"Content-Type": "application/json"},
                    )
                    urllib.request.urlopen(req, timeout=10)
                    log.info(
                        "Ollama: unloaded model %s (keep_alive=0)", self._current_model
                    )
                except Exception as e:
                    log.warning("Ollama: model unload failed: %s", e)
            self._current_model = None

    def is_ready(self) -> bool:
        import urllib.error
        import urllib.request

        try:
            resp = urllib.request.urlopen(f"{self.base_url}/api/tags", timeout=3)
            return resp.status == 200
        except (urllib.error.URLError, OSError, TimeoutError):
            return False

    async def generate(
        self,
        prompt: str,
        max_tokens: int = 128,
        temperature: float = 0.0,
        seed: int = 42,
    ) -> BackendRequestResult:
        payload = {
            "model": self._current_model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": temperature,
                "seed": seed,
            },
        }
        async with httpx.AsyncClient(timeout=self._timeout_s) as client:
            t0 = time.perf_counter()
            resp = await client.post(f"{self.base_url}/api/generate", json=payload)
            wall_ms = (time.perf_counter() - t0) * 1000

        if resp.status_code != 200:
            return BackendRequestResult(
                wall_ms=wall_ms, status=f"http_{resp.status_code}"
            )

        data = resp.json()
        ns_to_ms = 1e-6
        prompt_tokens = data.get("prompt_eval_count", 0)
        completion_tokens = data.get("eval_count", 0)
        prefill_ms = data.get("prompt_eval_duration", 0) * ns_to_ms
        decode_ms = data.get("eval_duration", 0) * ns_to_ms

        eff_tps = (completion_tokens / wall_ms * 1000) if wall_ms > 0 else 0.0
        gpu_tps = (completion_tokens / decode_ms * 1000) if decode_ms > 0 else None

        return BackendRequestResult(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            wall_ms=wall_ms,
            prefill_ms=prefill_ms,
            decode_ms=decode_ms,
            effective_tps=eff_tps,
            gpu_tokens_per_s=gpu_tps,
            response_text=data.get("response", ""),
            status="ok",
            backend_metadata={
                "total_duration_ms": data.get("total_duration", 0) * ns_to_ms,
                "load_duration_ms": data.get("load_duration", 0) * ns_to_ms,
            },
        )

    async def generate_stream(
        self,
        prompt: str,
        max_tokens: int = 128,
        temperature: float = 0.0,
        seed: int = 42,
    ) -> BackendStreamResult:
        payload = {
            "model": self._current_model,
            "prompt": prompt,
            "stream": True,
            "options": {
                "num_predict": max_tokens,
                "temperature": temperature,
                "seed": seed,
            },
        }
        ttft_ms = None
        completion_tokens = 0
        prompt_tokens = 0
        response_text = ""

        async with httpx.AsyncClient(timeout=self._timeout_s) as client:
            t0 = time.perf_counter()
            async with client.stream(
                "POST", f"{self.base_url}/api/generate", json=payload
            ) as resp:
                if resp.status_code != 200:
                    wall_ms = (time.perf_counter() - t0) * 1000
                    return BackendStreamResult(
                        wall_ms=wall_ms,
                        status=f"http_{resp.status_code}",
                    )
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    token_text = chunk.get("response", "")
                    if token_text and ttft_ms is None:
                        ttft_ms = (time.perf_counter() - t0) * 1000
                    response_text += token_text
                    if chunk.get("done", False):
                        completion_tokens = chunk.get("eval_count", 0)
                        prompt_tokens = chunk.get("prompt_eval_count", 0)
            wall_ms = (time.perf_counter() - t0) * 1000

        eff_tps = (completion_tokens / wall_ms * 1000) if wall_ms > 0 else 0.0
        return BackendStreamResult(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            wall_ms=wall_ms,
            effective_tps=eff_tps,
            response_text=response_text,
            ttft_ms=ttft_ms,
            status="ok",
        )


# ── vLLM ─────────────────────────────────────────────────────────────


class VllmBackend(ServingBackend):
    """vLLM backend (Docker container, OpenAI-compatible API)."""

    name = "vllm"
    quantization = "FP16"

    def __init__(self, cfg: dict):
        self.port = cfg.get("port", 8000)
        self._timeout_s = cfg.get("timeout_s", 180)
        self._docker_image = cfg.get("docker_image", "vllm/vllm-openai:latest")
        self._docker_name = cfg.get("docker_name", "tr130-vllm")
        self._extra_args = cfg.get("extra_args", [])
        self._current_model: str | None = None
        self._startup_timeout = cfg.get("startup_timeout_s", 300)

    def _hf_cache_path(self) -> str:
        """Resolve HF cache for volume mount."""
        hf_home = os.environ.get("HF_HOME", os.path.expanduser("~/.cache/huggingface"))
        return str(Path(hf_home).resolve())

    def start(
        self, model_hf_id: str, model_ollama_tag: str | None = None, **kwargs
    ) -> None:
        self._current_model = model_hf_id
        ensure_container_stopped(self._docker_name)

        env = {}
        hf_token = os.environ.get("HF_TOKEN", "")
        if hf_token:
            env["HF_TOKEN"] = hf_token

        volumes = {self._hf_cache_path(): "/root/.cache/huggingface"}

        model_args = ["--model", model_hf_id, *list(self._extra_args)]

        docker_run(
            name=self._docker_name,
            image=self._docker_image,
            ports={self.port: 8000},
            env=env,
            volumes=volumes,
            args=model_args,
            gpus="all",
        )

        log.info("Waiting for vLLM to be ready (model=%s)...", model_hf_id)
        if not self.wait_ready(timeout_s=self._startup_timeout):
            logs = docker_logs(self._docker_name, tail=80)
            raise RuntimeError(
                f"vLLM failed to start within {self._startup_timeout}s.\n"
                f"Logs:\n{logs}"
            )
        log.info("vLLM ready (model=%s)", model_hf_id)

    def stop(self) -> None:
        ensure_container_stopped(self._docker_name)
        log.info("vLLM container stopped")

    def is_ready(self) -> bool:
        import urllib.error
        import urllib.request

        try:
            resp = urllib.request.urlopen(f"{self.base_url}/health", timeout=5)
            return resp.status == 200
        except (urllib.error.URLError, OSError, TimeoutError):
            return False

    async def generate(
        self,
        prompt: str,
        max_tokens: int = 128,
        temperature: float = 0.0,
        seed: int = 42,
    ) -> BackendRequestResult:
        payload = {
            "model": self._current_model,
            "prompt": prompt,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "seed": seed,
        }
        async with httpx.AsyncClient(timeout=self._timeout_s) as client:
            t0 = time.perf_counter()
            resp = await client.post(f"{self.base_url}/v1/completions", json=payload)
            wall_ms = (time.perf_counter() - t0) * 1000

        if resp.status_code != 200:
            return BackendRequestResult(
                wall_ms=wall_ms,
                status=f"http_{resp.status_code}",
                backend_metadata={"error": resp.text[:500]},
            )

        data = resp.json()
        usage = data.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        text = data["choices"][0]["text"] if data.get("choices") else ""

        eff_tps = (completion_tokens / wall_ms * 1000) if wall_ms > 0 else 0.0

        return BackendRequestResult(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            wall_ms=wall_ms,
            prefill_ms=None,  # vLLM does not expose per-request breakdown
            decode_ms=None,
            effective_tps=eff_tps,
            gpu_tokens_per_s=None,
            response_text=text,
            status="ok",
        )

    async def generate_stream(
        self,
        prompt: str,
        max_tokens: int = 128,
        temperature: float = 0.0,
        seed: int = 42,
    ) -> BackendStreamResult:
        payload = {
            "model": self._current_model,
            "prompt": prompt,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "seed": seed,
            "stream": True,
        }
        ttft_ms = None
        completion_tokens = 0
        prompt_tokens = 0
        response_text = ""

        async with httpx.AsyncClient(timeout=self._timeout_s) as client:
            t0 = time.perf_counter()
            async with client.stream(
                "POST", f"{self.base_url}/v1/completions", json=payload
            ) as resp:
                if resp.status_code != 200:
                    wall_ms = (time.perf_counter() - t0) * 1000
                    return BackendStreamResult(
                        wall_ms=wall_ms,
                        status=f"http_{resp.status_code}",
                    )
                async for line in resp.aiter_lines():
                    line = line.strip()
                    if not line or line == "data: [DONE]":
                        continue
                    if line.startswith("data: "):
                        line = line[6:]
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    choices = chunk.get("choices", [])
                    if choices:
                        token_text = choices[0].get("text", "")
                        if token_text and ttft_ms is None:
                            ttft_ms = (time.perf_counter() - t0) * 1000
                        response_text += token_text
                    usage = chunk.get("usage")
                    if usage:
                        prompt_tokens = usage.get("prompt_tokens", 0)
                        completion_tokens = usage.get("completion_tokens", 0)
            wall_ms = (time.perf_counter() - t0) * 1000

        if completion_tokens == 0:
            # Estimate from response text (vLLM may not include usage in stream)
            completion_tokens = max(1, len(response_text.split()))

        eff_tps = (completion_tokens / wall_ms * 1000) if wall_ms > 0 else 0.0
        return BackendStreamResult(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            wall_ms=wall_ms,
            effective_tps=eff_tps,
            response_text=response_text,
            ttft_ms=ttft_ms,
            status="ok",
        )


# ── TGI ──────────────────────────────────────────────────────────────


class TgiBackend(ServingBackend):
    """HuggingFace Text Generation Inference (Docker, /generate)."""

    name = "tgi"
    quantization = "FP16"

    def __init__(self, cfg: dict):
        self.port = cfg.get("port", 8080)
        self._timeout_s = cfg.get("timeout_s", 180)
        self._docker_image = cfg.get(
            "docker_image",
            "ghcr.io/huggingface/text-generation-inference:latest",
        )
        self._docker_name = cfg.get("docker_name", "tr130-tgi")
        self._extra_args = cfg.get("extra_args", [])
        self._current_model: str | None = None
        self._startup_timeout = cfg.get("startup_timeout_s", 300)

    def _hf_cache_path(self) -> str:
        hf_home = os.environ.get("HF_HOME", os.path.expanduser("~/.cache/huggingface"))
        return str(Path(hf_home).resolve())

    def start(
        self, model_hf_id: str, model_ollama_tag: str | None = None, **kwargs
    ) -> None:
        self._current_model = model_hf_id
        ensure_container_stopped(self._docker_name)

        env = {}
        hf_token = os.environ.get("HF_TOKEN", "")
        if hf_token:
            env["HUGGING_FACE_HUB_TOKEN"] = hf_token

        volumes = {self._hf_cache_path(): "/data"}

        model_args = ["--model-id", model_hf_id, *list(self._extra_args)]

        docker_run(
            name=self._docker_name,
            image=self._docker_image,
            ports={self.port: 80},
            env=env,
            volumes=volumes,
            args=model_args,
            gpus="all",
            shm_size="1g",
        )

        log.info("Waiting for TGI to be ready (model=%s)...", model_hf_id)
        if not self.wait_ready(timeout_s=self._startup_timeout):
            logs = docker_logs(self._docker_name, tail=80)
            raise RuntimeError(
                f"TGI failed to start within {self._startup_timeout}s.\n"
                f"Logs:\n{logs}"
            )
        log.info("TGI ready (model=%s)", model_hf_id)

    def stop(self) -> None:
        ensure_container_stopped(self._docker_name)
        log.info("TGI container stopped")

    def is_ready(self) -> bool:
        import urllib.error
        import urllib.request

        try:
            resp = urllib.request.urlopen(f"{self.base_url}/health", timeout=5)
            return resp.status == 200
        except (urllib.error.URLError, OSError, TimeoutError):
            return False

    async def generate(
        self,
        prompt: str,
        max_tokens: int = 128,
        temperature: float = 0.0,
        seed: int = 42,
    ) -> BackendRequestResult:
        # TGI requires temperature > 0 (use 0.01 as effective zero)
        temp = max(temperature, 0.01)
        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": max_tokens,
                "temperature": temp,
                "seed": seed,
                "details": True,
                "decoder_input_details": False,
            },
        }
        async with httpx.AsyncClient(timeout=self._timeout_s) as client:
            t0 = time.perf_counter()
            resp = await client.post(f"{self.base_url}/generate", json=payload)
            wall_ms = (time.perf_counter() - t0) * 1000

        if resp.status_code != 200:
            return BackendRequestResult(
                wall_ms=wall_ms,
                status=f"http_{resp.status_code}",
                backend_metadata={"error": resp.text[:500]},
            )

        data = resp.json()
        # TGI may return [{...}] array instead of {...} object
        if isinstance(data, list):
            data = data[0] if data else {}
        generated_text = data.get("generated_text", "")
        details = data.get("details", {})
        completion_tokens = details.get("generated_tokens", 0)

        # TGI reports prefill tokens via the prefill array
        prefill_tokens = len(details.get("prefill", []))

        # Extract timing from response headers if available
        prefill_ms = None
        decode_ms = None
        headers = resp.headers
        if "x-inference-time" in headers:
            raw_val = float(headers["x-inference-time"])
            # TGI reports in seconds (typically 0.1-10s range).
            # If > 1000, assume microseconds (safety heuristic).
            total_inference_ms = raw_val / 1000 if raw_val > 1000 else raw_val * 1000
            decode_ms = total_inference_ms
        if "x-time-per-token" in headers:
            raw_tpt = float(headers["x-time-per-token"])
            # Same heuristic: values > 1000 are likely microseconds
            time_per_token_ms = raw_tpt / 1000 if raw_tpt > 1000 else raw_tpt * 1000
            decode_ms = time_per_token_ms * completion_tokens

        eff_tps = (completion_tokens / wall_ms * 1000) if wall_ms > 0 else 0.0
        gpu_tps = (
            (completion_tokens / decode_ms * 1000)
            if decode_ms and decode_ms > 0
            else None
        )

        return BackendRequestResult(
            prompt_tokens=prefill_tokens,
            completion_tokens=completion_tokens,
            wall_ms=wall_ms,
            prefill_ms=prefill_ms,
            decode_ms=decode_ms,
            effective_tps=eff_tps,
            gpu_tokens_per_s=gpu_tps,
            response_text=generated_text,
            status="ok",
            backend_metadata={
                "finish_reason": details.get("finish_reason", ""),
            },
        )

    async def generate_stream(
        self,
        prompt: str,
        max_tokens: int = 128,
        temperature: float = 0.0,
        seed: int = 42,
    ) -> BackendStreamResult:
        temp = max(temperature, 0.01)
        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": max_tokens,
                "temperature": temp,
                "seed": seed,
            },
        }
        ttft_ms = None
        completion_tokens = 0
        response_text = ""

        async with httpx.AsyncClient(timeout=self._timeout_s) as client:
            t0 = time.perf_counter()
            async with client.stream(
                "POST", f"{self.base_url}/generate_stream", json=payload
            ) as resp:
                if resp.status_code != 200:
                    wall_ms = (time.perf_counter() - t0) * 1000
                    return BackendStreamResult(
                        wall_ms=wall_ms,
                        status=f"http_{resp.status_code}",
                    )
                async for line in resp.aiter_lines():
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith("data:"):
                        line = line[5:].strip()
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    token_obj = chunk.get("token", {})
                    token_text = token_obj.get("text", "")
                    if token_text and ttft_ms is None:
                        ttft_ms = (time.perf_counter() - t0) * 1000
                    response_text += token_text
                    completion_tokens += 1
            wall_ms = (time.perf_counter() - t0) * 1000

        eff_tps = (completion_tokens / wall_ms * 1000) if wall_ms > 0 else 0.0
        return BackendStreamResult(
            completion_tokens=completion_tokens,
            wall_ms=wall_ms,
            effective_tps=eff_tps,
            response_text=response_text,
            ttft_ms=ttft_ms,
            status="ok",
        )


# ── Factory ──────────────────────────────────────────────────────────


def create_backend(name: str, cfg: dict) -> ServingBackend:
    """Factory: create a backend by name from config."""
    backends = {
        "ollama": OllamaBackend,
        "vllm": VllmBackend,
        "tgi": TgiBackend,
    }
    cls = backends.get(name)
    if cls is None:
        raise ValueError(f"Unknown backend: {name}. Options: {list(backends)}")
    return cls(cfg)
