"""Constants — quant levels, model registry, backends.

Extracted from TR133 research. No repo-specific paths or imports.
"""

from __future__ import annotations

# Quant ordering: highest precision first
QUANT_LEVELS = ["FP16", "Q8_0", "Q6_K", "Q5_K_M", "Q4_K_M", "Q3_K_S", "Q2_K"]

# Approximate bits-per-weight
QUANT_BPW: dict[str, float] = {
    "FP16": 16.0,
    "Q8_0": 8.0,
    "Q6_K": 6.5,
    "Q5_K_M": 5.5,
    "Q4_K_M": 4.5,
    "Q3_K_S": 3.5,
    "Q2_K": 2.5,
}

# Supported serving backends
BACKENDS = ["ollama", "vllm", "tgi"]

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
