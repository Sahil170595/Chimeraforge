"""TR136 shared utilities: model and backend definitions."""

from __future__ import annotations

import logging
from pathlib import Path
import sys

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from research.tr125.shared.utils import find_latest_run

logger = logging.getLogger("tr136.shared")

# TR136 models — small enough for FP16 on all backends, two families
TR136_MODELS = [
    {
        "name": "llama3.2-1b",
        "hf_id": "unsloth/Llama-3.2-1B-Instruct",
        "ollama_tag": "llama3.2:1b",
        "params_m": 1236,
        "family": "llama",
        "gated": False,
    },
    {
        "name": "llama3.2-3b",
        "hf_id": "unsloth/Llama-3.2-3B-Instruct",
        "ollama_tag": "llama3.2:3b",
        "params_m": 3213,
        "family": "llama",
        "gated": False,
    },
    {
        "name": "qwen2.5-1.5b",
        "hf_id": "Qwen/Qwen2.5-1.5B-Instruct",
        "ollama_tag": "qwen2.5:1.5b",
        "params_m": 1543,
        "family": "qwen",
        "gated": False,
    },
]

# Backend configurations for TR136
# Each (backend_name, label, quant) combination
TR136_BACKEND_CONFIGS = [
    {
        "name": "ollama",
        "label": "ollama_q4_k_m",
        "quant": "Q4_K_M",
        "config": {
            "port": 11434,
            "timeout_s": 120,
        },
        "ollama_tag_suffix": "-q4_K_M",  # appended to base ollama_tag
    },
    {
        "name": "ollama",
        "label": "ollama_q8_0",
        "quant": "Q8_0",
        "config": {
            "port": 11434,
            "timeout_s": 120,
        },
        "ollama_tag_suffix": "-q8_0",  # for instruct models
    },
    {
        "name": "vllm",
        "label": "vllm_fp16",
        "quant": "FP16",
        "config": {
            "port": 8000,
            "timeout_s": 180,
            "docker_image": "vllm/vllm-openai:latest",
            "docker_name": "tr136-vllm",
            "startup_timeout_s": 300,
            "extra_args": [
                "--max-model-len", "2048",
                "--dtype", "float16",
                "--enforce-eager",
                "--gpu-memory-utilization", "0.80",
            ],
        },
    },
    {
        "name": "tgi",
        "label": "tgi_fp16",
        "quant": "FP16",
        "config": {
            "port": 8080,
            "timeout_s": 180,
            "docker_image": "ghcr.io/huggingface/text-generation-inference:latest",
            "docker_name": "tr136-tgi",
            "startup_timeout_s": 300,
            "extra_args": [
                "--max-input-length", "1024",
                "--max-total-tokens", "2048",
            ],
        },
    },
]

# Map Ollama base tags to quant-specific tags
def get_ollama_quant_tag(base_tag: str, quant: str) -> str:
    """Get quant-specific Ollama tag from base tag and quant level."""
    # e.g. llama3.2:1b -> llama3.2:1b-instruct-q4_K_M
    base = base_tag.rstrip(":")
    # Handle tags like "llama3.2:1b" -> "llama3.2:1b-instruct-q4_K_M"
    if quant == "Q4_K_M":
        return f"{base}-instruct-q4_K_M"
    elif quant == "Q8_0":
        return f"{base}-instruct-q8_0"
    elif quant == "FP16":
        return f"{base}-instruct-fp16"
    return base

# Safety tasks
SAFETY_TASKS = {"advbench_refusal", "truthfulqa", "bbq_bias", "jailbreak_amplification"}
# Capability control tasks
CAPABILITY_TASKS = {"mmlu_real", "arc_challenge"}
ALL_TASKS = SAFETY_TASKS | CAPABILITY_TASKS

__all__ = [
    "TR136_MODELS",
    "TR136_BACKEND_CONFIGS",
    "SAFETY_TASKS",
    "CAPABILITY_TASKS",
    "ALL_TASKS",
    "get_ollama_quant_tag",
    "find_latest_run",
]
