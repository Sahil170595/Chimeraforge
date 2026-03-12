#!/usr/bin/env python3
"""
TR123: KV-Cache Production Economics — Two-Phase Measurement Engine.

Measures prefill and KV-cached decode separately for each
(model × backend × scenario × rep) cell, with CUDA event timing
and **per-phase** power sampling.

Fixes over v1:
- Phase-tagged power sampling (not whole-run average)
- Real text corpus (not word salad)
- Compile-aware warmup (5 runs for torch.compile, 2 for others)
- Thermal throttle detection + cooldown between model loads
- GPU clock speed recording
- No fake ONNX fallback (unsupported = skipped)

Outputs one JSONL record per measurement to results/{timestamp}/raw_measurements.jsonl.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
import logging
from pathlib import Path
import time
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

THERMAL_THROTTLE_C = 80  # Flag measurements above this temperature
COOLDOWN_SECONDS = 30  # Seconds to wait between model loads
COMPILE_WARMUP_RUNS = 5  # torch.compile needs more warmup for graph capture
DEFAULT_WARMUP_RUNS = 2

# ---------------------------------------------------------------------------
# Prompt corpus — real text, not word salad
# ---------------------------------------------------------------------------

# Excerpts from public-domain / freely-licensed sources, trimmed to approximate
# GPT-2 token counts.  Using real language matters because tokenization, attention
# patterns, and KV-cache access all depend on natural token distributions.

_PROMPT_CORPUS: dict[str, str] = {
    # ~64 tokens after GPT-2 tokenization
    "short": (
        "The transformer architecture, introduced in 2017, fundamentally changed "
        "natural language processing. By replacing recurrence with self-attention, "
        "transformers enabled parallel processing of entire sequences. The key "
        "innovation was the scaled dot-product attention mechanism, which computes "
        "relevance scores between all token pairs in a sequence."
    ),
    # ~256 tokens
    "medium": (
        "Large language models have become a central technology in artificial intelligence. "
        "These models, typically based on the transformer architecture, are trained on vast "
        "corpora of text data to predict the next token in a sequence. The training process "
        "involves two main phases: pre-training on general text data, and optional fine-tuning "
        "on specific tasks or instruction-following data.\n\n"
        "During inference, the model processes an input prompt through a series of transformer "
        "layers. Each layer contains a multi-head self-attention mechanism and a feed-forward "
        "network. The self-attention mechanism allows each token to attend to all previous "
        "tokens in the sequence, creating contextual representations that capture long-range "
        "dependencies.\n\n"
        "A critical optimization for inference is the key-value cache. During autoregressive "
        "generation, the model produces one token at a time. Without caching, each new token "
        "would require recomputing attention over the entire preceding sequence. The KV cache "
        "stores the key and value projections from previous tokens, so each decode step only "
        "needs to compute attention for the single new token against the cached values. This "
        "reduces the computational complexity of each decode step from O(n) to O(1) in the "
        "sequence length, at the cost of additional memory to store the cached tensors."
    ),
    # ~512 tokens
    "long": (
        "The economics of large language model inference present a complex optimization "
        "problem that balances computational cost, latency, throughput, and quality. "
        "Understanding these trade-offs is essential for deploying LLMs in production "
        "environments, where cost efficiency directly impacts business viability.\n\n"
        "Inference can be decomposed into two distinct phases with fundamentally different "
        "computational characteristics. The prefill phase processes the entire input prompt "
        "in parallel, producing the initial key-value cache. This phase is compute-bound: "
        "the GPU's arithmetic logic units are the bottleneck, and the operation achieves "
        "high arithmetic intensity. The decode phase generates tokens one at a time, each "
        "requiring a forward pass through the entire model but with only a single token as "
        "input. This phase is memory-bandwidth-bound: the bottleneck is reading the model "
        "weights and KV cache from GPU memory, while the actual computation per token is "
        "minimal.\n\n"
        "This phase asymmetry has profound implications for pricing and resource allocation. "
        "Commercial LLM providers typically charge more for output tokens than input tokens, "
        "reflecting the higher per-token cost of the decode phase. For a given hardware "
        "configuration, the prefill phase achieves much higher token throughput than decode. "
        "A single NVIDIA H100 GPU can prefill thousands of tokens per second but may only "
        "decode tens to hundreds of tokens per second, depending on the model size and "
        "batch configuration.\n\n"
        "The key-value cache introduces a memory-cost trade-off. Each cached token requires "
        "storing key and value tensors across all attention layers and heads. For a model "
        "like LLaMA-2 70B, the KV cache for a single sequence at 4096 tokens consumes "
        "approximately 1.25 GB with grouped-query attention, or roughly 1 percent of the "
        "model weight size. Without GQA, the cache would be much larger. As context lengths "
        "grow to 128K tokens or beyond, KV cache memory can exceed the model weights "
        "themselves, becoming the dominant memory consumer and limiting the number of "
        "concurrent requests a single GPU can serve.\n\n"
        "Consumer hardware adds additional constraints. Laptop GPUs like the NVIDIA RTX 4080 "
        "have limited VRAM, thermal throttling under sustained load, and dynamic clock speed "
        "adjustment based on power and thermal budgets. These factors make consumer-hardware "
        "inference economics qualitatively different from data center deployments, where GPUs "
        "operate at fixed clock speeds in temperature-controlled environments with dedicated "
        "cooling infrastructure."
    ),
    # ~1024 tokens (repeat long + additional)
    "very_long": (
        "The economics of large language model inference present a complex optimization "
        "problem that balances computational cost, latency, throughput, and quality. "
        "Understanding these trade-offs is essential for deploying LLMs in production "
        "environments, where cost efficiency directly impacts business viability.\n\n"
        "Inference can be decomposed into two distinct phases with fundamentally different "
        "computational characteristics. The prefill phase processes the entire input prompt "
        "in parallel, producing the initial key-value cache. This phase is compute-bound: "
        "the GPU's arithmetic logic units are the bottleneck, and the operation achieves "
        "high arithmetic intensity. The decode phase generates tokens one at a time, each "
        "requiring a forward pass through the entire model but with only a single token as "
        "input. This phase is memory-bandwidth-bound: the bottleneck is reading the model "
        "weights and KV cache from GPU memory, while the actual computation per token is "
        "minimal.\n\n"
        "This phase asymmetry has profound implications for pricing and resource allocation. "
        "Commercial LLM providers typically charge more for output tokens than input tokens, "
        "reflecting the higher per-token cost of the decode phase. For a given hardware "
        "configuration, the prefill phase achieves much higher token throughput than decode.\n\n"
        "The key-value cache introduces a memory-cost trade-off. Each cached token requires "
        "storing key and value tensors across all attention layers and heads. For a model "
        "like LLaMA-2 70B, the KV cache for a single sequence at 4096 tokens consumes "
        "approximately 1.25 GB with grouped-query attention. As context lengths grow to "
        "128K tokens or beyond, KV cache memory can exceed the model weights themselves.\n\n"
        "Consumer hardware adds additional constraints. Laptop GPUs have limited VRAM, "
        "thermal throttling under sustained load, and dynamic clock speed adjustment. These "
        "factors make consumer-hardware inference economics qualitatively different from "
        "data center deployments.\n\n"
        "Quantization offers one path to reducing both memory and compute costs. By "
        "representing weights and activations in lower precision formats like INT8 or INT4, "
        "models can run faster and use less memory. The key-value cache itself can be "
        "quantized: FP8 quantization reduces cache memory by half with minimal quality "
        "loss, while INT4 quantization cuts memory by four times but may introduce "
        "noticeable degradation for certain tasks.\n\n"
        "Batching is another critical optimization. By processing multiple requests "
        "simultaneously, the cost of reading model weights from memory is amortized across "
        "all requests in the batch. This is particularly effective for the decode phase, "
        "where the model weights are the dominant memory access. Continuous batching, where "
        "new requests are added to the batch as old ones complete, maximizes GPU utilization "
        "by avoiding the throughput loss from padding shorter sequences.\n\n"
        "The serving stack also impacts economics. Frameworks like vLLM, TensorRT-LLM, and "
        "SGLang implement various optimizations including PagedAttention for efficient KV "
        "cache memory management, speculative decoding for faster generation, and kernel "
        "fusion for reduced overhead. The choice of serving framework can reduce cost per "
        "token by 25-40 percent compared to naive HuggingFace inference.\n\n"
        "Energy consumption is an often-overlooked component of inference cost. A single "
        "GPU running continuous inference consumes 200-400 watts, translating to significant "
        "electricity costs at scale. The energy cost per token varies between phases: "
        "prefill draws higher power due to full GPU utilization, while decode draws less "
        "power but takes more time per token. Accurate phase-split energy accounting "
        "requires sampling power at high frequency and tagging each sample with the active "
        "inference phase, an approach pioneered by the TokenPowerBench framework."
    ),
}


def _get_prompt_for_scenario(scenario_name: str, target_tokens: int) -> str:
    """Select an appropriate prompt from the corpus based on target token count."""
    if target_tokens <= 96:
        return _PROMPT_CORPUS["short"]
    if target_tokens <= 384:
        return _PROMPT_CORPUS["medium"]
    if target_tokens <= 768:
        return _PROMPT_CORPUS["long"]
    return _PROMPT_CORPUS["very_long"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _now_run_id() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


def _git_head() -> str | None:
    import subprocess

    try:
        out = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=_repo_root())
        return out.decode("utf-8").strip()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# GPU state queries
# ---------------------------------------------------------------------------


def _gpu_snapshot() -> dict[str, Any]:
    """Capture current GPU clock speed, temperature, and power."""
    try:
        import pynvml

        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        result: dict[str, Any] = {}

        try:
            result["gpu_clock_mhz"] = pynvml.nvmlDeviceGetClockInfo(
                handle, pynvml.NVML_CLOCK_SM
            )
        except Exception:
            result["gpu_clock_mhz"] = None

        try:
            result["gpu_temp_c"] = pynvml.nvmlDeviceGetTemperature(
                handle, pynvml.NVML_TEMPERATURE_GPU
            )
        except Exception:
            result["gpu_temp_c"] = None

        try:
            result["gpu_power_w"] = pynvml.nvmlDeviceGetPowerUsage(handle) / 1000.0
        except Exception:
            result["gpu_power_w"] = None

        try:
            mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
            result["gpu_mem_used_mb"] = mem.used / (1024**2)
            result["gpu_mem_total_mb"] = mem.total / (1024**2)
        except Exception:
            pass

        pynvml.nvmlShutdown()
        return result
    except Exception:
        return {}


def _gpu_cooldown(target_temp_c: int = 65, max_wait_s: int = 60):
    """Wait for GPU temperature to drop below target. Used between model loads."""
    snap = _gpu_snapshot()
    temp = snap.get("gpu_temp_c")
    if temp is None or temp <= target_temp_c:
        return

    logger.info(f"  GPU at {temp}°C, cooling down (target: {target_temp_c}°C)...")
    start = time.time()
    while time.time() - start < max_wait_s:
        time.sleep(5)
        snap = _gpu_snapshot()
        temp = snap.get("gpu_temp_c")
        if temp is None or temp <= target_temp_c:
            logger.info(f"  GPU cooled to {temp}°C")
            return
    logger.warning(f"  Cooldown timeout ({max_wait_s}s), GPU still at {temp}°C")


# ---------------------------------------------------------------------------
# Phase-aware power sampler
# ---------------------------------------------------------------------------


class PhasePowerSampler:
    """Lightweight per-phase GPU power sampler.

    Unlike the shared ResourceMonitor (which wraps the whole measurement),
    this tags each power sample with the currently-active phase so we can
    compute per-phase power means for accurate energy attribution.
    """

    def __init__(self, interval_s: float = 0.05):
        self.interval_s = interval_s
        self.samples: list[
            tuple[float, str, float | None, float | None, int | None]
        ] = []
        # (timestamp, phase, power_w, temp_c, clock_mhz)
        self._phase = "idle"
        self._running = False
        self._thread = None
        self._nvml_ok = False

    def start(self):
        self._running = True
        try:
            import pynvml

            pynvml.nvmlInit()
            self._nvml_ok = True
        except Exception:
            self._nvml_ok = False

        import threading

        self._thread = threading.Thread(target=self._sample_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        if self._nvml_ok:
            try:
                import pynvml

                pynvml.nvmlShutdown()
            except Exception:
                pass
            self._nvml_ok = False

    def mark_phase(self, phase: str):
        """Call this to tag subsequent samples with a phase name."""
        self._phase = phase

    def _sample_loop(self):
        while self._running:
            power_w = None
            temp_c = None
            clock_mhz = None
            if self._nvml_ok:
                try:
                    import pynvml

                    handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                    power_w = pynvml.nvmlDeviceGetPowerUsage(handle) / 1000.0
                    temp_c = pynvml.nvmlDeviceGetTemperature(
                        handle, pynvml.NVML_TEMPERATURE_GPU
                    )
                    clock_mhz = pynvml.nvmlDeviceGetClockInfo(
                        handle, pynvml.NVML_CLOCK_SM
                    )
                except Exception:
                    pass
            self.samples.append((time.time(), self._phase, power_w, temp_c, clock_mhz))
            time.sleep(self.interval_s)

    def get_phase_metrics(self) -> dict[str, dict[str, Any]]:
        """Compute per-phase power/temp/clock statistics."""
        from collections import defaultdict

        phase_data: dict[str, dict[str, list]] = defaultdict(
            lambda: {"power": [], "temp": [], "clock": []}
        )
        for _, phase, power, temp, clock in self.samples:
            if power is not None:
                phase_data[phase]["power"].append(power)
            if temp is not None:
                phase_data[phase]["temp"].append(temp)
            if clock is not None:
                phase_data[phase]["clock"].append(clock)

        result = {}
        for phase, data in phase_data.items():
            metrics: dict[str, Any] = {"samples": len(data["power"])}
            if data["power"]:
                metrics["power_mean_w"] = sum(data["power"]) / len(data["power"])
                metrics["power_max_w"] = max(data["power"])
            if data["temp"]:
                metrics["temp_mean_c"] = sum(data["temp"]) / len(data["temp"])
                metrics["temp_max_c"] = max(data["temp"])
                metrics["thermal_throttled"] = max(data["temp"]) >= THERMAL_THROTTLE_C
            if data["clock"]:
                metrics["clock_mean_mhz"] = sum(data["clock"]) / len(data["clock"])
                metrics["clock_min_mhz"] = min(data["clock"])
            result[phase] = metrics
        return result


# ---------------------------------------------------------------------------
# CUDA event timer
# ---------------------------------------------------------------------------


def _cuda_event_timer(device_type: str):
    """Returns a timing function using CUDA events, or None for CPU."""
    if device_type != "cuda":
        return None
    try:
        import torch

        if not torch.cuda.is_available():
            return None
        start = torch.cuda.Event(enable_timing=True)
        end = torch.cuda.Event(enable_timing=True)

        def time_fn(fn):
            torch.cuda.synchronize()
            start.record()
            out = fn()
            end.record()
            torch.cuda.synchronize()
            return float(start.elapsed_time(end)), out

        return time_fn
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Model loading
# ---------------------------------------------------------------------------


def _load_hf(
    model_path: str,
    device: str,
    compile_model: bool = False,
    trust_remote_code: bool = False,
):
    """Load a HuggingFace model and tokenizer.

    Uses float16 on CUDA for consistency with cost/memory formulas.
    Falls back to float32 on CPU (float16 has no CPU kernel benefit).

    For gated models (e.g. meta-llama/*), requires HF_TOKEN env var or
    prior `huggingface-cli login`. The from_pretrained call will download
    the model if not already cached.
    """
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tok = AutoTokenizer.from_pretrained(model_path, trust_remote_code=trust_remote_code)
    if getattr(tok, "pad_token", None) is None:
        tok.pad_token = tok.eos_token

    dtype = torch.float16 if device == "cuda" else torch.float32
    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        torch_dtype=dtype,
        trust_remote_code=trust_remote_code,
    )
    model.eval()
    dev = torch.device("cuda" if device == "cuda" else "cpu")
    model.to(dev)

    if compile_model and device == "cuda":
        try:
            model = torch.compile(model)
            logger.info("torch.compile applied")
        except Exception as e:
            logger.warning(f"torch.compile failed: {e}")

    return tok, model, dev


def _load_onnx(model_path: str, device: str):
    """Load an ONNX model. Returns (tokenizer, session, provider_name)."""
    from transformers import AutoTokenizer

    tok = AutoTokenizer.from_pretrained(model_path)
    if getattr(tok, "pad_token", None) is None:
        tok.pad_token = tok.eos_token

    onnx_dir = _repo_root() / "models" / "onnx" / model_path.replace("/", "_")
    onnx_path = onnx_dir / "model.onnx"
    if not onnx_path.exists():
        return None, None, f"ONNX model not found at {onnx_path}"

    import onnxruntime as ort

    providers = (
        ["CUDAExecutionProvider", "CPUExecutionProvider"]
        if device == "cuda"
        else ["CPUExecutionProvider"]
    )
    session = ort.InferenceSession(str(onnx_path), providers=providers)
    active_provider = session.get_providers()[0]

    # Check if this model has KV-cache support
    input_names = [inp.name for inp in session.get_inputs()]
    output_names = [out.name for out in session.get_outputs()]
    has_kv = any("past" in n or "present" in n for n in input_names + output_names)
    if not has_kv:
        return (
            None,
            None,
            "ONNX model lacks KV-cache IO (no past/present nodes). Cannot do two-phase measurement.",
        )

    return tok, session, active_provider


# ---------------------------------------------------------------------------
# Two-phase measurement: HuggingFace
# ---------------------------------------------------------------------------


def _measure_hf_two_phase(
    *,
    tok,
    model,
    device,
    prompt: str,
    gen_tokens: int,
    memory_snapshots: bool = True,
    power_sampler: PhasePowerSampler | None = None,
) -> dict[str, Any]:
    """Measure prefill and KV-cached decode separately for HuggingFace models."""
    import torch

    enc = tok(prompt, return_tensors="pt", add_special_tokens=True)
    input_ids = enc["input_ids"].to(device)
    attention_mask = enc.get("attention_mask")
    if attention_mask is not None:
        attention_mask = attention_mask.to(device)
    seq_len = int(input_ids.shape[1])
    prompt_tokens = (
        int(attention_mask.sum().item()) if attention_mask is not None else seq_len
    )

    timer = _cuda_event_timer("cuda" if device.type == "cuda" else "cpu")

    gpu_peak_prefill_mb = None
    gpu_peak_total_mb = None
    if memory_snapshots and device.type == "cuda":
        torch.cuda.reset_peak_memory_stats()

    # --- Phase 1: Prefill ---
    if power_sampler:
        power_sampler.mark_phase("prefill")

    def prefill_call():
        with torch.no_grad():
            return model(
                input_ids=input_ids,
                attention_mask=attention_mask,
                use_cache=True,
            )

    prefill_start = time.perf_counter()
    if timer is not None:
        prefill_cuda_ms, out = timer(prefill_call)
    else:
        out = prefill_call()
        prefill_cuda_ms = None
    prefill_ms = (time.perf_counter() - prefill_start) * 1000.0

    past = getattr(out, "past_key_values", None)
    if past is None:
        if power_sampler:
            power_sampler.mark_phase("idle")
        return {
            "status": "error",
            "error": "missing_past_key_values",
            "prompt_tokens": prompt_tokens,
            "gen_tokens": gen_tokens,
        }

    # Memory after prefill (sync first for accurate reading)
    if memory_snapshots and device.type == "cuda":
        torch.cuda.synchronize()
        gpu_peak_prefill_mb = float(torch.cuda.max_memory_allocated()) / (1024**2)

    # --- Phase 2: KV-Cached Decode ---
    if power_sampler:
        power_sampler.mark_phase("decode")

    generated_tokens = 0

    def decode_loop():
        nonlocal generated_tokens
        next_token = input_ids[:, -1:]
        kv = past
        with torch.no_grad():
            for _ in range(gen_tokens):
                r = model(
                    input_ids=next_token,
                    attention_mask=None,
                    past_key_values=kv,
                    use_cache=True,
                )
                kv = r.past_key_values
                next_token = torch.argmax(r.logits[:, -1, :], dim=-1, keepdim=True)
                generated_tokens += 1

    decode_start = time.perf_counter()
    if timer is not None:
        decode_cuda_ms, _ = timer(lambda: decode_loop())
    else:
        decode_loop()
        decode_cuda_ms = None
    decode_ms = (time.perf_counter() - decode_start) * 1000.0

    if power_sampler:
        power_sampler.mark_phase("idle")

    # Memory after decode
    if memory_snapshots and device.type == "cuda":
        torch.cuda.synchronize()
        gpu_peak_total_mb = float(torch.cuda.max_memory_allocated()) / (1024**2)

    # Snapshot GPU state at end of measurement
    gpu_state = _gpu_snapshot()

    return {
        "status": "ok",
        "error": "",
        "prompt_tokens": prompt_tokens,
        "gen_tokens": generated_tokens,
        "seq_len": seq_len,
        "prefill_ms": prefill_ms,
        "prefill_cuda_ms": prefill_cuda_ms,
        "decode_ms": decode_ms,
        "decode_cuda_ms": decode_cuda_ms,
        "total_ms": prefill_ms + decode_ms,
        "gpu_peak_prefill_mb": gpu_peak_prefill_mb,
        "gpu_peak_total_mb": gpu_peak_total_mb,
        "gpu_clock_mhz": gpu_state.get("gpu_clock_mhz"),
        "gpu_temp_c": gpu_state.get("gpu_temp_c"),
    }


# ---------------------------------------------------------------------------
# Two-phase measurement: ONNX (KV-cache required)
# ---------------------------------------------------------------------------


def _measure_onnx_two_phase(
    *,
    tok,
    session,
    prompt: str,
    gen_tokens: int,
    power_sampler: PhasePowerSampler | None = None,
) -> dict[str, Any]:
    """Measure prefill and decode for ONNX models with KV-cache support.

    Models without KV-cache IO are rejected at load time — no fake O(n²) fallback.
    """
    import numpy as np

    enc = tok(prompt, return_tensors="np", add_special_tokens=True)
    input_ids = enc["input_ids"]
    attention_mask = enc.get("attention_mask", np.ones_like(input_ids))
    prompt_tokens = int(attention_mask.sum())

    input_names = [inp.name for inp in session.get_inputs()]
    output_names = [out.name for out in session.get_outputs()]

    # --- Prefill ---
    if power_sampler:
        power_sampler.mark_phase("prefill")

    prefill_start = time.perf_counter()
    feeds = {"input_ids": input_ids}
    if "attention_mask" in input_names:
        feeds["attention_mask"] = attention_mask
    outputs = session.run(output_names, feeds)
    prefill_ms = (time.perf_counter() - prefill_start) * 1000.0

    kv_outputs = {
        n: v
        for n, v in zip(output_names, outputs, strict=False)
        if "present" in n or "key" in n or "value" in n
    }
    logits_out = outputs[0]

    # --- Decode ---
    if power_sampler:
        power_sampler.mark_phase("decode")

    decode_start = time.perf_counter()
    next_token = np.argmax(logits_out[:, -1, :], axis=-1, keepdims=True).astype(
        np.int64
    )
    for step in range(gen_tokens):
        feeds = {"input_ids": next_token}
        if "attention_mask" in input_names:
            new_len = int(input_ids.shape[1]) + step + 1
            feeds["attention_mask"] = np.ones((1, new_len), dtype=np.int64)
        for kn, kv in kv_outputs.items():
            past_name = kn.replace("present", "past_key_values")
            if past_name in input_names:
                feeds[past_name] = kv
        outputs = session.run(output_names, feeds)
        logits_out = outputs[0]
        kv_outputs = {
            n: v
            for n, v in zip(output_names, outputs, strict=False)
            if "present" in n or "key" in n or "value" in n
        }
        next_token = np.argmax(logits_out[:, -1, :], axis=-1, keepdims=True).astype(
            np.int64
        )
    decode_ms = (time.perf_counter() - decode_start) * 1000.0

    if power_sampler:
        power_sampler.mark_phase("idle")

    return {
        "status": "ok",
        "error": "",
        "prompt_tokens": prompt_tokens,
        "gen_tokens": gen_tokens,
        "seq_len": int(input_ids.shape[1]),
        "prefill_ms": prefill_ms,
        "prefill_cuda_ms": None,
        "decode_ms": decode_ms,
        "decode_cuda_ms": None,
        "total_ms": prefill_ms + decode_ms,
        "gpu_peak_prefill_mb": None,
        "gpu_peak_total_mb": None,
        "gpu_clock_mhz": None,
        "gpu_temp_c": None,
    }


# ---------------------------------------------------------------------------
# Two-phase measurement: Ollama
# ---------------------------------------------------------------------------


def _measure_ollama_two_phase(
    *,
    url: str,
    model: str,
    prompt: str,
    gen_tokens: int,
    timeout_s: float = 120.0,
) -> dict[str, Any]:
    """Measure prefill and decode using Ollama's native phase timing."""
    import urllib.request

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"num_predict": gen_tokens},
    }
    req = urllib.request.Request(
        f"{url}/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    wall_start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            body = resp.read().decode("utf-8")
        data = json.loads(body)
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "prompt_tokens": 0,
            "gen_tokens": 0,
        }
    wall_ms = (time.perf_counter() - wall_start) * 1000.0

    prompt_tokens = int(data.get("prompt_eval_count") or 0)
    eval_tokens = int(data.get("eval_count") or 0)
    # Ollama durations are in nanoseconds
    prefill_ms = float(data.get("prompt_eval_duration") or 0) / 1e6
    decode_ms = float(data.get("eval_duration") or 0) / 1e6
    load_ms = float(data.get("load_duration") or 0) / 1e6

    return {
        "status": "ok",
        "error": "",
        "prompt_tokens": prompt_tokens,
        "gen_tokens": eval_tokens,
        "seq_len": prompt_tokens,
        "prefill_ms": prefill_ms,
        "prefill_cuda_ms": None,
        "decode_ms": decode_ms,
        "decode_cuda_ms": None,
        "total_ms": prefill_ms + decode_ms,
        "wall_ms": wall_ms,
        "load_ms": load_ms,
        "gpu_peak_prefill_mb": None,
        "gpu_peak_total_mb": None,
        "gpu_clock_mhz": None,
        "gpu_temp_c": None,
    }


# ---------------------------------------------------------------------------
# Single measurement with phase-aware power sampling
# ---------------------------------------------------------------------------


def _run_single(
    *,
    spec: dict[str, Any],
    model_obj: Any,
    tok: Any,
    device: Any,
    cfg: dict[str, Any],
) -> dict[str, Any]:
    """Run a single measurement cell with phase-tagged power sampling."""
    backend = spec["backend"]
    prompt = _get_prompt_for_scenario(spec["scenario"], spec["prompt_tokens"])
    gen_tokens = spec["generate_tokens"]
    measurement_cfg = cfg.get("measurement", {})

    # Start phase-aware power sampler
    use_power = measurement_cfg.get("resource_monitor", False)
    sampler = None
    if use_power:
        try:
            sampler = PhasePowerSampler(
                interval_s=measurement_cfg.get("monitor_interval_s", 0.05)
            )
            sampler.start()
        except Exception:
            sampler = None

    try:
        if backend.startswith("transformers"):
            result = _measure_hf_two_phase(
                tok=tok,
                model=model_obj,
                device=device,
                prompt=prompt,
                gen_tokens=gen_tokens,
                memory_snapshots=measurement_cfg.get("memory_snapshots", True),
                power_sampler=sampler,
            )
        elif backend.startswith("onnxruntime"):
            result = _measure_onnx_two_phase(
                tok=tok,
                session=model_obj,
                prompt=prompt,
                gen_tokens=gen_tokens,
                power_sampler=sampler,
            )
        else:
            result = {"status": "error", "error": f"unknown backend: {backend}"}

    except Exception as e:
        if sampler:
            sampler.stop()
        return {
            "status": "error",
            "error": str(e),
            "prompt_tokens": spec["prompt_tokens"],
            "gen_tokens": gen_tokens,
        }

    # Collect phase-tagged power metrics
    if sampler:
        sampler.stop()
        phase_metrics = sampler.get_phase_metrics()
        result["phase_power"] = phase_metrics

        # Flag thermal throttling
        for phase_name, metrics in phase_metrics.items():
            if metrics.get("thermal_throttled"):
                result.setdefault("warnings", []).append(
                    f"thermal_throttle_during_{phase_name}"
                )

    return result


# ---------------------------------------------------------------------------
# Matrix runner
# ---------------------------------------------------------------------------


def _check_vram_for_model(model_cfg: dict[str, Any], backend: str) -> str | None:
    """Check if GPU has enough VRAM for this model. Returns skip reason or None."""
    if "cpu" in backend:
        return None  # CPU backends don't use VRAM
    fp16_vram_gb = model_cfg.get("fp16_vram_gb", 0)
    if fp16_vram_gb <= 0:
        return None  # No VRAM estimate, try anyway
    try:
        import torch

        if not torch.cuda.is_available():
            return "CUDA not available"
        free_mem = torch.cuda.mem_get_info(0)[0] / (1024**3)
        # Need model weights + ~2GB overhead for KV cache/activations/CUDA context
        needed = fp16_vram_gb + 2.0
        if free_mem < needed:
            return f"Insufficient VRAM: {free_mem:.1f}GB free, need ~{needed:.1f}GB"
    except Exception:
        pass
    return None


def run_matrix(config_path: str | Path) -> Path:
    """Run the full experiment matrix and write results to JSONL."""
    config_path = Path(config_path)
    with open(config_path) as f:
        cfg = yaml.safe_load(f)

    run_id = _now_run_id()
    repo_root = _repo_root()
    results_dir = (
        repo_root
        / cfg.get("output", {}).get("results_dir", "research/tr123/results")
        / run_id
    )
    results_dir.mkdir(parents=True, exist_ok=True)

    jsonl_path = results_dir / "raw_measurements.jsonl"
    manifest_path = results_dir / "manifest.json"

    models = cfg["models"]
    backends = cfg["backends"]
    scenarios = cfg["scenarios"]
    reps = cfg.get("repetitions", 7)
    default_warmup = cfg.get("warmup_runs", DEFAULT_WARMUP_RUNS)
    seed = cfg.get("seed", 42)
    backend_skip = cfg.get("backend_skip", {})

    # Compute actual cell count (accounting for backend_skip)
    total_cells = 0
    for m in models:
        skips = backend_skip.get(m["name"], [])
        model_backends = [b for b in backends if b not in skips]
        total_cells += len(model_backends) * len(scenarios) * reps

    manifest = {
        "tr": "TR123",
        "run_id": run_id,
        "config": str(config_path),
        "git_head": _git_head(),
        "started": datetime.now(UTC).isoformat(),
        "models": [m["name"] for m in models],
        "backends": backends,
        "scenarios": [s["name"] for s in scenarios],
        "repetitions": reps,
        "warmup_runs": default_warmup,
        "compile_warmup_runs": COMPILE_WARMUP_RUNS,
        "seed": seed,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    cell_num = 0

    logger.info(f"TR123 benchmark: {total_cells} measurement cells → {jsonl_path}")

    with open(jsonl_path, "w", encoding="utf-8") as f_out:
        for model_cfg in models:
            model_name = model_cfg["name"]
            skip_backends = backend_skip.get(model_name, [])
            trust_remote_code = model_cfg.get("trust_remote_code", False)

            for backend in backends:
                # Check backend_skip from config
                if backend in skip_backends:
                    logger.info(
                        f"  SKIP {model_name}/{backend}: "
                        f"excluded in backend_skip config"
                    )
                    for scenario in scenarios:
                        for rep in range(reps):
                            record = {
                                "timestamp": datetime.now(UTC).isoformat(),
                                "model": model_name,
                                "backend": backend,
                                "scenario": scenario["name"],
                                "rep": rep,
                                "status": "skipped",
                                "error": "backend_skip config",
                            }
                            f_out.write(json.dumps(record) + "\n")
                    continue

                # Check VRAM before attempting to load
                vram_issue = _check_vram_for_model(model_cfg, backend)
                if vram_issue:
                    logger.warning(f"  SKIP {model_name}/{backend}: {vram_issue}")
                    for scenario in scenarios:
                        for rep in range(reps):
                            record = {
                                "timestamp": datetime.now(UTC).isoformat(),
                                "model": model_name,
                                "backend": backend,
                                "scenario": scenario["name"],
                                "rep": rep,
                                "status": "skipped",
                                "error": vram_issue,
                            }
                            f_out.write(json.dumps(record) + "\n")
                    continue

                # Cooldown between model loads to normalize thermal state
                _gpu_cooldown()

                logger.info(f"  Loading {model_name} for {backend}...")
                tok, model_obj, device = None, None, None

                try:
                    if backend == "transformers-gpu-compile":
                        tok, model_obj, device = _load_hf(
                            model_cfg["path"],
                            "cuda",
                            compile_model=True,
                            trust_remote_code=trust_remote_code,
                        )
                    elif backend == "transformers-gpu":
                        tok, model_obj, device = _load_hf(
                            model_cfg["path"],
                            "cuda",
                            compile_model=False,
                            trust_remote_code=trust_remote_code,
                        )
                    elif backend == "transformers-cpu":
                        tok, model_obj, device = _load_hf(
                            model_cfg["path"],
                            "cpu",
                            compile_model=False,
                            trust_remote_code=trust_remote_code,
                        )
                    elif backend.startswith("onnxruntime"):
                        ort_device = "cuda" if "gpu" in backend else "cpu"
                        tok, model_obj, provider_info = _load_onnx(
                            model_cfg["path"], ort_device
                        )
                        if tok is None:
                            logger.warning(
                                f"  SKIP {model_name}/{backend}: {provider_info}"
                            )
                            for scenario in scenarios:
                                for rep in range(reps):
                                    record = {
                                        "timestamp": datetime.now(UTC).isoformat(),
                                        "model": model_name,
                                        "backend": backend,
                                        "scenario": scenario["name"],
                                        "rep": rep,
                                        "status": "skipped",
                                        "error": str(provider_info),
                                    }
                                    f_out.write(json.dumps(record) + "\n")
                            continue
                        device = ort_device
                except Exception as e:
                    logger.error(f"  FAIL loading {model_name}/{backend}: {e}")
                    for scenario in scenarios:
                        for rep in range(reps):
                            record = {
                                "timestamp": datetime.now(UTC).isoformat(),
                                "model": model_name,
                                "backend": backend,
                                "scenario": scenario["name"],
                                "rep": rep,
                                "status": "error",
                                "error": f"load_failed: {e}",
                            }
                            f_out.write(json.dumps(record) + "\n")
                    continue

                # Compile-aware warmup count
                warmup = (
                    COMPILE_WARMUP_RUNS
                    if backend == "transformers-gpu-compile"
                    else default_warmup
                )

                for scenario in scenarios:
                    spec = {
                        "backend": backend,
                        "model": model_name,
                        "scenario": scenario["name"],
                        "prompt_tokens": scenario["prompt_tokens"],
                        "generate_tokens": scenario["generate_tokens"],
                    }

                    # Warmup runs (not recorded)
                    for w in range(warmup):
                        logger.debug(
                            f"    Warmup {w + 1}/{warmup}: "
                            f"{model_name}/{backend}/{scenario['name']}"
                        )
                        _run_single(
                            spec=spec,
                            model_obj=model_obj,
                            tok=tok,
                            device=device,
                            cfg=cfg,
                        )

                    # Measured runs
                    for rep in range(reps):
                        cell_num += 1
                        logger.info(
                            f"  [{cell_num}/{total_cells}] "
                            f"{model_name}/{backend}/{scenario['name']} "
                            f"rep={rep}"
                        )

                        result = _run_single(
                            spec=spec,
                            model_obj=model_obj,
                            tok=tok,
                            device=device,
                            cfg=cfg,
                        )

                        record = {
                            "timestamp": datetime.now(UTC).isoformat(),
                            "model": model_name,
                            "backend": backend,
                            "scenario": scenario["name"],
                            "rep": rep,
                            **result,
                        }
                        f_out.write(json.dumps(record) + "\n")
                        f_out.flush()

                # Free model memory aggressively for large models
                del model_obj, tok
                if (
                    device is not None
                    and hasattr(device, "type")
                    and device.type == "cuda"
                ):
                    import gc

                    import torch

                    gc.collect()
                    torch.cuda.empty_cache()
                    torch.cuda.synchronize()

    manifest["finished"] = datetime.now(UTC).isoformat()
    manifest["total_cells"] = cell_num
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    logger.info(f"TR123 benchmark complete: {cell_num} cells → {jsonl_path}")
    return results_dir


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="TR123: KV-Cache Production Economics Benchmark"
    )
    parser.add_argument(
        "--config",
        type=str,
        default=str(Path(__file__).parent / "configs" / "matrix.yaml"),
    )
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    results_dir = run_matrix(args.config)
    print(f"\nResults: {results_dir}")


if __name__ == "__main__":
    main()
