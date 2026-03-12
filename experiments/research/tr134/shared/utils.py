"""TR134 shared utilities across phases.

Provides:
- TR134 model definitions and quantization level subsets
- Ollama tag construction (delegates to TR125 helpers)
- Result directory discovery
"""

from __future__ import annotations

import logging
from pathlib import Path
import sys

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from research.tr125.shared.utils import (
    OLLAMA_BASE_TAGS,
    OLLAMA_QUANT_SUFFIXES,
    QUANT_BPW,
    QUANT_PRECISION_ORDER,
    build_ollama_tag,
    extract_base_model,
    extract_quant_level,
    find_latest_run,
    list_local_ollama_tags,
)

logger = logging.getLogger("tr134.shared")

# -- TR134 model definitions ---------------------------------------------------

TR134_MODELS: dict[str, str] = {
    "llama3.2-1b": "llama3.2:1b-instruct",
    "llama3.2-3b": "llama3.2:3b-instruct",
    "mistral-7b": "mistral:7b-instruct-v0.3",
    "qwen2.5-7b": "qwen2.5:7b-instruct",
}

# 7B models that skip FP16 (too large, use Q8_0 as highest-precision baseline)
TR134_7B_MODELS: set[str] = {"mistral-7b", "qwen2.5-7b"}

# Models that support all 7 quant levels including FP16
TR134_SMALL_MODELS: set[str] = {"llama3.2-1b", "llama3.2-3b"}

# All 7 quantization levels (Phase 2 full matrix)
TR134_ALL_QUANTS: list[str] = [
    "FP16",
    "Q8_0",
    "Q6_K",
    "Q5_K_M",
    "Q4_K_M",
    "Q3_K_S",
    "Q2_K",
]

# Phase 1 subset: 3 levels (high, medium, low)
TR134_PHASE1_QUANTS: list[str] = ["FP16", "Q4_K_M", "Q2_K"]

# Safety task names
SAFETY_TASKS = {"advbench_refusal", "truthfulqa", "bbq_bias"}

# Jailbreak task names (Phase 3)
JAILBREAK_TASKS = {"jailbreak_amplification"}

# All safety-related tasks including jailbreak (Phase 3)
ALL_SAFETY_TASKS = SAFETY_TASKS | JAILBREAK_TASKS

# Capability task names (Phase 2+)
CAPABILITY_TASKS = {"mmlu_real", "arc_challenge"}

# Quant levels for 7B models (no FP16)
TR134_7B_QUANTS: list[str] = [
    "Q8_0",
    "Q6_K",
    "Q5_K_M",
    "Q4_K_M",
    "Q3_K_S",
    "Q2_K",
]


def build_model_quant_matrix(
    models: dict[str, str] | None = None,
    quants: list[str] | None = None,
    respect_7b_limits: bool = True,
) -> list[dict[str, str]]:
    """Build list of {name, base_tag, quant, ollama_tag} for the model×quant matrix.

    Returns one entry per (model, quant) combination.
    If respect_7b_limits=True, 7B models skip FP16 (use Q8_0 as baseline).
    """
    if models is None:
        models = TR134_MODELS
    if quants is None:
        quants = TR134_ALL_QUANTS

    entries = []
    for model_name, base_tag in models.items():
        model_quants = quants
        if respect_7b_limits and model_name in TR134_7B_MODELS:
            model_quants = [q for q in quants if q != "FP16"]
        for quant in model_quants:
            tag = build_ollama_tag(base_tag, quant)
            config_name = f"{model_name}-{quant.lower()}" if quant != "FP16" else f"{model_name}-fp16"
            entries.append(
                {
                    "name": config_name,
                    "base_model": model_name,
                    "base_tag": base_tag,
                    "quant": quant,
                    "ollama_tag": tag,
                }
            )
    return entries


# Re-export for convenience
__all__ = [
    "TR134_MODELS",
    "TR134_7B_MODELS",
    "TR134_SMALL_MODELS",
    "TR134_ALL_QUANTS",
    "TR134_7B_QUANTS",
    "TR134_PHASE1_QUANTS",
    "SAFETY_TASKS",
    "JAILBREAK_TASKS",
    "ALL_SAFETY_TASKS",
    "CAPABILITY_TASKS",
    "QUANT_PRECISION_ORDER",
    "QUANT_BPW",
    "OLLAMA_BASE_TAGS",
    "OLLAMA_QUANT_SUFFIXES",
    "build_ollama_tag",
    "build_model_quant_matrix",
    "extract_base_model",
    "extract_quant_level",
    "find_latest_run",
    "list_local_ollama_tags",
]
