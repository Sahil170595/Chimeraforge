"""Constants - quant levels, model registry, backends.

Extracted from TR133 research. No repo-specific paths or imports.
"""

from __future__ import annotations

# Canonical search ladder for the planner's quant sweep (highest precision first).
QUANT_LEVELS = ["FP16", "Q8_0", "Q6_K", "Q5_K_M", "Q4_K_M", "Q3_K_S", "Q2_K"]

# Approximate effective bits-per-weight (incl. GGUF block/scale overhead). Broader
# than QUANT_LEVELS so a model's *native* quant (e.g. an Ollama `q4_0`/`IQ4_XS`
# tag) resolves to a real VRAM footprint instead of silently defaulting to FP16.
QUANT_BPW: dict[str, float] = {
    "FP32": 32.0,
    "FP16": 16.0,
    "BF16": 16.0,
    "Q8_0": 8.0,
    "Q6_K": 6.5,
    "Q5_K_M": 5.5,
    "Q5_K_S": 5.4,
    "Q5_1": 6.0,
    "Q5_0": 5.5,
    "Q4_K_M": 4.5,
    "Q4_K_S": 4.4,
    "Q4_1": 5.0,
    "Q4_0": 4.5,
    "Q3_K_L": 4.3,
    "Q3_K_M": 3.9,
    "Q3_K_S": 3.5,
    "Q2_K": 2.5,
    "Q2_K_S": 2.3,
    "IQ4_NL": 4.5,
    "IQ4_XS": 4.25,
    "IQ3_S": 3.4,
    "IQ3_XXS": 3.06,
    "IQ2_M": 2.7,
    "IQ2_XXS": 2.06,
    "IQ1_S": 1.56,
}

# Supported serving backends
BACKENDS = ["ollama", "vllm", "tgi"]

# Which backends do continuous (in-flight) batching -- one GPU serves many
# sequences concurrently, amortizing weight reads. Ollama (llama.cpp) effectively
# serves one stream per slot, so it is modelled at batch=1 (replicas, not batch).
BACKEND_CONTINUOUS_BATCHING: dict[str, bool] = {
    "ollama": False,
    "vllm": True,
    "tgi": True,
}

# Decode compute-utilisation ceiling for batched decode (when large batches turn
# the FC/MLP kernels compute-bound). Decode is mostly memory-bound, so this acts
# as a safety cap rarely reached on consumer GPUs.
DECODE_COMPUTE_MFU = 0.5

# Workload service-time variance (squared coefficient of variation, Cs^2) presets.
# Analytical queueing is conservative for low-variance traffic but under-estimates
# the tail for high-variance/agent workloads (heavy-tailed service: a few requests
# run 100x longer and hold a slot). Cs^2=0 is deterministic (reproduces M/D/1).
WORKLOAD_CV2: dict[str, float] = {
    "steady": 0.0,  # fixed-length, deterministic
    "chatbot": 1.0,  # variable output length (typical)
    "bursty": 4.0,  # mixed short/long
    "agent": 8.0,  # heavy-tailed (long tool calls / multi-turn)
}

# At/above this Cs^2 the analytical p95 is not trustworthy on its own -- warn and
# advise a real load test / simulation (the head-of-line-blocking regime).
HIGH_VARIANCE_CV2 = 4.0

# Roofline throughput estimate for off-registry models. Decode is memory-bound:
# each token streams all weights once, so tok/s ~= MBU * bandwidth / weight_bytes.
# MBU (memory-bandwidth utilisation) calibrated from the llama3.2-1b ollama FP16
# datapoint: 146.33 tok/s / (556 GB/s / 2.48 GB) = 0.65 (see models.ThroughputModel).
MBU_DEFAULT = 0.65

# Default architecture used only when a model's real config cannot be resolved.
DEFAULT_ARCH: dict[str, int] = {"n_layers": 32, "n_kv_heads": 8, "d_head": 128}
DEFAULT_PARAMS_B = 3.0

# Fraction of VRAM a batched server can devote to KV-cache after weights +
# activations + framework overhead. PagedAttention packs KV at block granularity,
# so realised utilisation is high but not 1.0. Used to bound concurrent sequences.
KV_CACHE_UTILISATION = 0.9

# KV-cache element size in bytes. Backends keep KV in FP16 even when weights are
# quantized (KV quantization is not yet modelled here).
KV_DTYPE_BYTES = 2

# Prefill is compute-bound: ~2 FLOPs per parameter per prompt token. MFU (model
# FLOPs utilisation) discounts peak TFLOPS to realised; 0.3-0.5 is typical for a
# single-stream forward pass. Calibratable later from measured TTFT.
FLOPS_PER_PARAM_PER_TOKEN = 2
PREFILL_MFU = 0.4

# Default prompt (input) length in tokens for TTFT estimation when unspecified.
DEFAULT_PROMPT_TOKENS = 512

# Model registry: params in billions
MODEL_PARAMS_B: dict[str, float] = {
    "qwen2.5-0.5b": 0.49,
    "llama3.2-1b": 1.24,
    "qwen2.5-1.5b": 1.54,
    "phi-2": 2.78,
    "qwen2.5-3b": 3.09,
    "llama3.2-3b": 3.21,
    "llama3.1-8b": 8.03,
}

# Canonical architecture/family per registry model. Used to resolve arbitrary
# identifiers (Ollama tags, HF paths) to a registry model by family + params
# rather than exact name (see planner.identity).
MODEL_FAMILY: dict[str, str] = {
    "qwen2.5-0.5b": "qwen2.5",
    "llama3.2-1b": "llama3.2",
    "qwen2.5-1.5b": "qwen2.5",
    "phi-2": "phi",
    "qwen2.5-3b": "qwen2.5",
    "llama3.2-3b": "llama3.2",
    "llama3.1-8b": "llama3.1",
}

# Architecture metadata for KV-cache formula
MODEL_ARCH: dict[str, dict[str, int]] = {
    "qwen2.5-0.5b": {"n_layers": 24, "n_kv_heads": 2, "d_head": 64},
    "llama3.2-1b": {"n_layers": 16, "n_kv_heads": 8, "d_head": 64},
    "qwen2.5-1.5b": {"n_layers": 28, "n_kv_heads": 2, "d_head": 128},
    "phi-2": {"n_layers": 32, "n_kv_heads": 32, "d_head": 80},
    "qwen2.5-3b": {"n_layers": 36, "n_kv_heads": 2, "d_head": 128},
    "llama3.2-3b": {"n_layers": 28, "n_kv_heads": 8, "d_head": 128},
    "llama3.1-8b": {"n_layers": 32, "n_kv_heads": 8, "d_head": 128},
}
