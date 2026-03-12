"""TR135 shared utilities: model definitions, concurrency levels."""

from __future__ import annotations

import logging
from pathlib import Path
import sys

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from research.tr125.shared.utils import find_latest_run

logger = logging.getLogger("tr135.shared")

# TR135 models: 3 sizes spanning 1B-7B, two families (Llama, Qwen), all at Q4_K_M
TR135_MODELS = {
    "llama3.2-1b-q4_k_m": {
        "ollama_tag": "llama3.2:1b-instruct-q4_K_M",
        "hf_id": "meta-llama/Llama-3.2-1B-Instruct",
        "params_m": 1236,
        "family": "llama",
        "quant": "Q4_K_M",
    },
    "llama3.2-3b-q4_k_m": {
        "ollama_tag": "llama3.2:3b-instruct-q4_K_M",
        "hf_id": "meta-llama/Llama-3.2-3B-Instruct",
        "params_m": 3213,
        "family": "llama",
        "quant": "Q4_K_M",
    },
    "qwen2.5-3b-q4_k_m": {
        "ollama_tag": "qwen2.5:3b-instruct-q4_K_M",
        "hf_id": "Qwen/Qwen2.5-3B-Instruct",
        "params_m": 3090,
        "family": "qwen",
        "quant": "Q4_K_M",
    },
}

# Concurrency levels
N_AGENT_LEVELS = [1, 2, 4, 8]

# Safety tasks (reuse TR134 task files)
SAFETY_TASKS = {"advbench_refusal", "truthfulqa", "bbq_bias", "jailbreak_amplification"}

# Capability control tasks
CAPABILITY_TASKS = {"mmlu_real", "arc_challenge"}

ALL_TASKS = SAFETY_TASKS | CAPABILITY_TASKS

__all__ = [
    "TR135_MODELS",
    "N_AGENT_LEVELS",
    "SAFETY_TASKS",
    "CAPABILITY_TASKS",
    "ALL_TASKS",
    "find_latest_run",
]
