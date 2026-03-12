#!/usr/bin/env python3
"""
TR123: KV-Cache Memory Overhead Analysis.

Theoretical and empirical measurement of KV-cache memory consumption.
Implements the standard formula:
    KV_bytes = 2 × L × B × T × H_kv × D_h × precision_bytes

References:
- Brenndoerfer (2025): KV Cache Memory Calculation for LLM Inference
- "Keep the Cost Down" (arXiv:2407.18003): KV-Cache Optimization Survey
"""

from __future__ import annotations

import argparse
import csv
import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model architecture specs
# ---------------------------------------------------------------------------

# Model architectures for KV-cache analysis.
# MHA models: n_kv_heads == n_heads (every head stores its own KV)
# GQA models: n_kv_heads < n_heads (multiple query heads share KV)
MODEL_ARCHITECTURES: dict[str, dict[str, int]] = {
    "gpt2": {
        "n_layers": 12,
        "n_heads": 12,
        "n_kv_heads": 12,  # MHA
        "d_head": 64,
        "d_model": 768,
        "params_m": 124,
    },
    "llama-3.2-1b": {
        "n_layers": 16,
        "n_heads": 32,
        "n_kv_heads": 8,  # GQA: 4 query heads per KV head
        "d_head": 64,
        "d_model": 2048,
        "params_m": 1236,
    },
    "qwen2.5-1.5b": {
        "n_layers": 28,
        "n_heads": 12,
        "n_kv_heads": 2,  # GQA: 6 query heads per KV head (extreme)
        "d_head": 128,
        "d_model": 1536,
        "params_m": 1543,
    },
    "phi-2": {
        "n_layers": 32,
        "n_heads": 32,
        "n_kv_heads": 32,  # MHA
        "d_head": 80,
        "d_model": 2560,
        "params_m": 2700,
    },
    "llama-3.2-3b": {
        "n_layers": 28,
        "n_heads": 24,
        "n_kv_heads": 8,  # GQA: 3 query heads per KV head
        "d_head": 128,
        "d_model": 3072,
        "params_m": 3213,
    },
}


# ---------------------------------------------------------------------------
# Theoretical formula
# ---------------------------------------------------------------------------


def kv_cache_bytes(
    n_layers: int,
    n_kv_heads: int,
    d_head: int,
    seq_len: int,
    batch_size: int = 1,
    precision_bytes: int = 2,
) -> int:
    """Compute theoretical KV-cache memory in bytes.

    Formula: 2 × L × B × T × H_kv × D_h × precision_bytes
    - Factor 2 accounts for both Key and Value matrices
    - L = number of transformer layers
    - B = batch size
    - T = sequence length (tokens cached)
    - H_kv = number of KV heads (equals n_heads for MHA, < n_heads for GQA)
    - D_h = dimension per head
    - precision_bytes = 2 for FP16/BF16, 4 for FP32
    """
    return 2 * n_layers * batch_size * seq_len * n_kv_heads * d_head * precision_bytes


def kv_cache_mb(
    n_layers: int,
    n_kv_heads: int,
    d_head: int,
    seq_len: int,
    batch_size: int = 1,
    precision_bytes: int = 2,
) -> float:
    """Compute theoretical KV-cache memory in MB."""
    return kv_cache_bytes(
        n_layers, n_kv_heads, d_head, seq_len, batch_size, precision_bytes
    ) / (1024**2)


def model_weight_bytes(params_millions: int, precision_bytes: int = 2) -> int:
    """Compute model weight size in bytes.

    Default precision_bytes=2 (FP16) matches run_benchmark.py which loads
    models with torch_dtype=torch.float16 on CUDA.
    """
    return int(params_millions * 1e6) * precision_bytes


def compute_crossover_point(
    params_millions: int,
    n_layers: int,
    n_kv_heads: int,
    d_head: int,
    batch_size: int = 1,
    precision_bytes: int = 2,
) -> int:
    """Find sequence length where KV-cache equals model weight size.

    At this crossover, cache memory becomes the dominant memory consumer.
    Returns the crossover sequence length in tokens.
    """
    weight_bytes = model_weight_bytes(params_millions, precision_bytes)
    # KV_bytes = 2 * L * B * T * H_kv * D_h * prec
    # Solve for T: T = weight_bytes / (2 * L * B * H_kv * D_h * prec)
    denominator = 2 * n_layers * batch_size * n_kv_heads * d_head * precision_bytes
    if denominator == 0:
        return 0
    return int(weight_bytes / denominator)


# ---------------------------------------------------------------------------
# Empirical measurement
# ---------------------------------------------------------------------------


def measure_kv_cache_memory(
    model_path: str,
    context_lengths: list[int],
    trust_remote_code: bool = False,
) -> list[dict[str, Any]]:
    """Empirically measure KV-cache memory by inspecting past_key_values tensor sizes.

    Instead of using memory_allocated() delta (which includes logits, intermediates,
    and allocator fragmentation), we directly compute the size of the KV tensors
    returned by the model.

    Returns a list of measurements, one per context length.
    """
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    if not torch.cuda.is_available():
        logger.warning("CUDA not available, skipping empirical KV-cache measurement")
        return []

    tok = AutoTokenizer.from_pretrained(model_path, trust_remote_code=trust_remote_code)
    if getattr(tok, "pad_token", None) is None:
        tok.pad_token = tok.eos_token
    # Use float16 to match run_benchmark.py (consistency with cost formulas)
    model = AutoModelForCausalLM.from_pretrained(
        model_path, torch_dtype=torch.float16, trust_remote_code=trust_remote_code
    )
    model.eval()
    device = torch.device("cuda")
    model.to(device)

    # Clamp context lengths to model's max_position_embeddings to avoid
    # CUDA index-out-of-bounds errors (e.g., GPT-2 max is 1024).
    max_pos = getattr(model.config, "max_position_embeddings", None)

    results = []
    for ctx_len in context_lengths:
        effective_len = ctx_len
        if max_pos is not None and ctx_len > max_pos:
            logger.info(
                f"  {model_path}: clamping ctx_len {ctx_len} → {max_pos} (max_position_embeddings)"
            )
            effective_len = max_pos

        torch.cuda.empty_cache()

        # Use valid token IDs from the tokenizer's vocabulary
        input_ids = torch.randint(0, tok.vocab_size, (1, effective_len), device=device)

        with torch.no_grad():
            out = model(input_ids=input_ids, use_cache=True)

        torch.cuda.synchronize()

        # Directly measure KV tensor sizes (not memory_allocated delta)
        past = getattr(out, "past_key_values", None)
        kv_bytes = 0
        if past is not None:
            for layer_kv in past:
                # Each layer returns (key, value) tensors
                for tensor in layer_kv:
                    if hasattr(tensor, "nelement"):
                        kv_bytes += tensor.nelement() * tensor.element_size()

        kv_mb = kv_bytes / (1024**2)

        # Also measure full allocation delta for comparison
        del out.logits  # Free logits before measuring
        torch.cuda.synchronize()
        alloc_after = torch.cuda.memory_allocated()

        del out, past
        torch.cuda.synchronize()
        alloc_cleaned = torch.cuda.memory_allocated()

        results.append(
            {
                "model": model_path,
                "context_length": ctx_len,
                "effective_context_length": effective_len,
                "kv_cache_empirical_mb": round(kv_mb, 3),
                "kv_cache_empirical_bytes": kv_bytes,
                "precision": "fp16",
                "alloc_with_kv_mb": round(alloc_after / (1024**2), 3),
                "alloc_after_cleanup_mb": round(alloc_cleaned / (1024**2), 3),
            }
        )
        logger.info(
            f"  {model_path} ctx={effective_len}: KV={kv_mb:.3f} MB (direct tensor measurement)"
        )

    del model
    torch.cuda.empty_cache()
    return results


# ---------------------------------------------------------------------------
# Memory overhead table
# ---------------------------------------------------------------------------


def compute_memory_overhead_table(
    models: list[dict[str, Any]],
    context_lengths: list[int],
    precision_bytes: int = 2,
) -> list[dict[str, Any]]:
    """Compute theoretical KV-cache memory for each model × context length.

    Also computes the ratio of KV-cache to model weights.
    """
    rows = []
    for model in models:
        name = model["name"]
        arch = MODEL_ARCHITECTURES.get(name) or model.get("architecture", {})
        if not arch:
            logger.warning(f"No architecture info for {name}, skipping")
            continue

        params_m = arch.get("params_m", model.get("params_m", 0))
        weight_mb = model_weight_bytes(params_m, precision_bytes) / (1024**2)

        for ctx_len in context_lengths:
            cache_mb = kv_cache_mb(
                n_layers=arch["n_layers"],
                n_kv_heads=arch["n_kv_heads"],
                d_head=arch["d_head"],
                seq_len=ctx_len,
                precision_bytes=precision_bytes,
            )
            ratio = cache_mb / weight_mb if weight_mb > 0 else 0.0

            rows.append(
                {
                    "model": name,
                    "params_m": params_m,
                    "context_length": ctx_len,
                    "kv_cache_theoretical_mb": round(cache_mb, 3),
                    "model_weights_mb": round(weight_mb, 1),
                    "cache_to_weights_ratio": round(ratio, 4),
                }
            )

    return rows


def compute_break_even(
    kv_memory_gb: float,
    memory_cost_per_gb_hr: float,
    latency_savings_per_req_s: float,
    compute_cost_per_gpu_hr: float,
) -> dict[str, float]:
    """Compute break-even request rate where KV-cache memory cost equals latency savings.

    Args:
        kv_memory_gb: KV-cache memory overhead in GB
        memory_cost_per_gb_hr: Cost of GPU memory per GB per hour
        latency_savings_per_req_s: Time saved per request by using KV cache (seconds)
        compute_cost_per_gpu_hr: GPU compute cost per hour

    Returns:
        break_even_req_per_hr: Requests per hour at break-even
        memory_cost_per_hr: Hourly cost of KV-cache memory
        savings_per_req: Dollar savings per request from reduced latency
    """
    memory_cost_per_hr = kv_memory_gb * memory_cost_per_gb_hr
    savings_per_req = (latency_savings_per_req_s / 3600.0) * compute_cost_per_gpu_hr

    if savings_per_req <= 0:
        return {
            "break_even_req_per_hr": float("inf"),
            "memory_cost_per_hr": memory_cost_per_hr,
            "savings_per_req": 0.0,
        }

    break_even = memory_cost_per_hr / savings_per_req

    return {
        "break_even_req_per_hr": round(break_even, 1),
        "memory_cost_per_hr": round(memory_cost_per_hr, 6),
        "savings_per_req": round(savings_per_req, 8),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(config_path: str | Path, results_dir: str | Path | None = None):
    """Run KV-cache memory analysis and write results."""
    config_path = Path(config_path)
    with open(config_path) as f:
        cfg = yaml.safe_load(f)

    if results_dir is None:
        results_dir = Path(__file__).parent / "results" / "kv_cache_analysis"
    results_dir = Path(results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)

    models = cfg["models"]
    kv_cfg = cfg.get("kv_cache", {})
    context_lengths = kv_cfg.get("context_lengths", [64, 128, 256, 512, 1024, 2048])

    # Theoretical analysis
    logger.info("Computing theoretical KV-cache memory overhead...")
    theoretical = compute_memory_overhead_table(models, context_lengths)

    theoretical_path = results_dir / "kv_memory_theoretical.csv"
    if theoretical:
        with open(theoretical_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=theoretical[0].keys())
            w.writeheader()
            w.writerows(theoretical)
        logger.info(f"  Wrote {len(theoretical)} rows → {theoretical_path}")

    # Crossover points
    crossover_rows = []
    for model in models:
        name = model["name"]
        arch = MODEL_ARCHITECTURES.get(name, {})
        if not arch:
            continue
        crossover = compute_crossover_point(
            params_millions=arch["params_m"],
            n_layers=arch["n_layers"],
            n_kv_heads=arch["n_kv_heads"],
            d_head=arch["d_head"],
        )
        crossover_rows.append(
            {
                "model": name,
                "params_m": arch["params_m"],
                "crossover_tokens": crossover,
            }
        )
        logger.info(f"  {name}: crossover at {crossover:,} tokens")

    crossover_path = results_dir / "kv_crossover_points.csv"
    if crossover_rows:
        with open(crossover_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=crossover_rows[0].keys())
            w.writeheader()
            w.writerows(crossover_rows)

    # Empirical measurement (if GPU available)
    if kv_cfg.get("measure_memory_overhead", False):
        logger.info("Running empirical KV-cache memory measurements...")
        empirical_rows = []
        for model in models:
            try:
                rows = measure_kv_cache_memory(
                    model["path"],
                    context_lengths,
                    trust_remote_code=model.get("trust_remote_code", False),
                )
                empirical_rows.extend(rows)
            except Exception as e:
                logger.error(f"  Failed empirical measurement for {model['name']}: {e}")

        if empirical_rows:
            empirical_path = results_dir / "kv_memory_empirical.csv"
            with open(empirical_path, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=empirical_rows[0].keys())
                w.writeheader()
                w.writerows(empirical_rows)
            logger.info(f"  Wrote {len(empirical_rows)} rows → {empirical_path}")

    logger.info("KV-cache analysis complete.")
    return results_dir


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TR123: KV-Cache Memory Analysis")
    parser.add_argument(
        "--config",
        default=str(Path(__file__).parent / "configs" / "matrix.yaml"),
    )
    parser.add_argument("--results-dir", default=None)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    main(args.config, args.results_dir)
