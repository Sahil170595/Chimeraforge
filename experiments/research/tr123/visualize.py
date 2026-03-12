#!/usr/bin/env python3
"""
TR123: Visualization — 8 plot types for KV-Cache Production Economics.

1. Phase cost stacked bar chart
2. Cached vs uncached comparison
3. Energy per phase heatmap
4. KV memory scaling curve (theoretical + empirical)
5. Crossover analysis
6. Break-even surface
7. Latency CDF per backend
8. Cost tier comparison bar chart
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


def _load_csv(path: Path) -> list[dict[str, Any]]:
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _safe_float(v: Any) -> float | None:
    if v is None or v == "" or v == "None":
        return None
    try:
        val = float(v)
        return val if val == val else None  # NaN check
    except (ValueError, TypeError):
        return None


def _ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Plot 1: Phase cost stacked bar chart
# ---------------------------------------------------------------------------


def plot_phase_cost_bar(summary: list[dict], plots_dir: Path, model: str = "gpt2"):
    """Stacked bar: $/1M tokens (prefill + decode) per backend for a given model."""
    import matplotlib.pyplot as plt

    rows = [r for r in summary if r.get("model") == model]
    if not rows:
        logger.warning(f"No data for model {model} in summary")
        return

    # Average across scenarios for each backend
    from collections import defaultdict

    backend_costs: dict[str, dict[str, list]] = defaultdict(
        lambda: {"prefill": [], "decode": []}
    )
    for r in rows:
        pc = _safe_float(r.get("prefill_cost_per_1m_mean"))
        dc = _safe_float(r.get("decode_cost_per_1m_mean"))
        if pc is not None and dc is not None:
            backend_costs[r["backend"]]["prefill"].append(pc)
            backend_costs[r["backend"]]["decode"].append(dc)

    backends = sorted(backend_costs.keys())
    prefill_means = [np.mean(backend_costs[b]["prefill"]) for b in backends]
    decode_means = [np.mean(backend_costs[b]["decode"]) for b in backends]

    _fig, ax = plt.subplots(figsize=(10, 6))
    x = np.arange(len(backends))
    ax.bar(x, prefill_means, label="Prefill (input tokens)", color="#2196F3")
    ax.bar(
        x,
        decode_means,
        bottom=prefill_means,
        label="Decode (output tokens)",
        color="#FF9800",
    )
    ax.set_xlabel("Backend")
    ax.set_ylabel("$/1M tokens")
    ax.set_title(f"Phase-Split Cost per 1M Tokens — {model}")
    ax.set_xticks(x)
    ax.set_xticklabels(backends, rotation=30, ha="right")
    ax.legend()
    plt.tight_layout()
    plt.savefig(plots_dir / f"phase_cost_bar_{model}.png", dpi=150)
    plt.close()
    logger.info(f"  Saved phase_cost_bar_{model}.png")


# ---------------------------------------------------------------------------
# Plot 2: Cached vs uncached comparison
# ---------------------------------------------------------------------------


def plot_cached_vs_uncached(improvement: list[dict], plots_dir: Path):
    """Grouped bars: TR119 uncached vs TR123 cached cost."""
    import matplotlib.pyplot as plt

    rows = [
        r
        for r in improvement
        if _safe_float(r.get("tr119_uncached_cost_per_1m"))
        and _safe_float(r.get("tr123_cached_cost_per_1m"))
    ]
    if not rows:
        logger.warning("No improvement data available for cached vs uncached plot")
        return

    labels = [f"{r['model']}\n{r['backend']}" for r in rows]
    uncached = [_safe_float(r["tr119_uncached_cost_per_1m"]) for r in rows]
    cached = [_safe_float(r["tr123_cached_cost_per_1m"]) for r in rows]

    _fig, ax = plt.subplots(figsize=(12, 6))
    x = np.arange(len(labels))
    w = 0.35
    ax.bar(x - w / 2, uncached, w, label="TR119 Uncached", color="#EF5350")
    ax.bar(x + w / 2, cached, w, label="TR123 KV-Cached", color="#66BB6A")
    ax.set_ylabel("$/1M tokens")
    ax.set_title("Production Cost: Uncached vs KV-Cached Inference")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    ax.legend()
    plt.tight_layout()
    plt.savefig(plots_dir / "cached_vs_uncached.png", dpi=150)
    plt.close()
    logger.info("  Saved cached_vs_uncached.png")


# ---------------------------------------------------------------------------
# Plot 3: Energy per phase heatmap
# ---------------------------------------------------------------------------


def plot_energy_heatmap(summary: list[dict], plots_dir: Path):
    """Heatmap: model × backend, color = total J/tok."""
    import matplotlib.pyplot as plt

    models = sorted({r.get("model", "") for r in summary})
    backends = sorted({r.get("backend", "") for r in summary})

    data = np.full((len(models), len(backends)), np.nan)
    for r in summary:
        pj = _safe_float(r.get("prefill_j_per_tok_mean"))
        dj = _safe_float(r.get("decode_j_per_tok_mean"))
        if pj is not None and dj is not None:
            mi = models.index(r["model"])
            bi = backends.index(r["backend"])
            data[mi, bi] = pj + dj

    if np.all(np.isnan(data)):
        logger.warning("No energy data for heatmap")
        return

    _fig, ax = plt.subplots(figsize=(10, 6))
    im = ax.imshow(data, cmap="YlOrRd", aspect="auto")
    ax.set_xticks(range(len(backends)))
    ax.set_xticklabels(backends, rotation=30, ha="right")
    ax.set_yticks(range(len(models)))
    ax.set_yticklabels(models)
    ax.set_title("Energy per Token (J/tok) — Prefill + Decode")
    plt.colorbar(im, label="J/tok")

    for i in range(len(models)):
        for j in range(len(backends)):
            if not np.isnan(data[i, j]):
                ax.text(j, i, f"{data[i, j]:.4f}", ha="center", va="center", fontsize=8)

    plt.tight_layout()
    plt.savefig(plots_dir / "energy_heatmap.png", dpi=150)
    plt.close()
    logger.info("  Saved energy_heatmap.png")


# ---------------------------------------------------------------------------
# Plot 4: KV memory scaling curve
# ---------------------------------------------------------------------------


def plot_kv_memory_scaling(results_dir: Path, plots_dir: Path):
    """Line chart: context length vs KV-cache memory (theoretical + empirical)."""
    import matplotlib.pyplot as plt

    theoretical_path = results_dir / "kv_cache_analysis" / "kv_memory_theoretical.csv"
    empirical_path = results_dir / "kv_cache_analysis" / "kv_memory_empirical.csv"

    if not theoretical_path.exists():
        logger.warning("No theoretical KV memory data")
        return

    theoretical = _load_csv(theoretical_path)

    models = sorted({r["model"] for r in theoretical})
    _fig, ax = plt.subplots(figsize=(10, 6))

    colors = [
        "#2196F3",
        "#FF9800",
        "#4CAF50",
        "#9C27B0",
        "#F44336",
        "#795548",
        "#00BCD4",
    ]
    for i, model in enumerate(models):
        model_rows = [r for r in theoretical if r["model"] == model]
        ctx = [int(r["context_length"]) for r in model_rows]
        mem = [float(r["kv_cache_theoretical_mb"]) for r in model_rows]
        ax.plot(
            ctx,
            mem,
            marker="o",
            label=f"{model} (theoretical)",
            color=colors[i % len(colors)],
        )

    # Overlay empirical if available
    if empirical_path.exists():
        empirical = _load_csv(empirical_path)
        for i, model in enumerate(models):
            model_rows = [r for r in empirical if model in r.get("model", "")]
            if model_rows:
                ctx = [int(r["context_length"]) for r in model_rows]
                mem = [float(r["kv_cache_empirical_mb"]) for r in model_rows]
                ax.plot(
                    ctx,
                    mem,
                    marker="x",
                    linestyle="--",
                    label=f"{model} (empirical)",
                    color=colors[i % len(colors)],
                    alpha=0.7,
                )

    ax.set_xlabel("Context Length (tokens)")
    ax.set_ylabel("KV-Cache Memory (MB)")
    ax.set_title("KV-Cache Memory Scaling")
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(plots_dir / "kv_memory_scaling.png", dpi=150)
    plt.close()
    logger.info("  Saved kv_memory_scaling.png")


# ---------------------------------------------------------------------------
# Plot 5: Crossover analysis
# ---------------------------------------------------------------------------


def plot_crossover(results_dir: Path, plots_dir: Path):
    """Bar chart: crossover point (tokens) where KV cache = model weights."""
    import matplotlib.pyplot as plt

    crossover_path = results_dir / "kv_cache_analysis" / "kv_crossover_points.csv"
    if not crossover_path.exists():
        logger.warning("No crossover data")
        return

    data = _load_csv(crossover_path)
    models = [r["model"] for r in data]
    crossovers = [int(r["crossover_tokens"]) for r in data]

    _fig, ax = plt.subplots(figsize=(8, 5))
    ax.barh(models, crossovers, color="#7E57C2")
    ax.set_xlabel("Crossover Sequence Length (tokens)")
    ax.set_title("KV-Cache = Model Weights Crossover Point")
    for i, v in enumerate(crossovers):
        ax.text(v + 100, i, f"{v:,}", va="center", fontsize=9)
    plt.tight_layout()
    plt.savefig(plots_dir / "kv_crossover.png", dpi=150)
    plt.close()
    logger.info("  Saved kv_crossover.png")


# ---------------------------------------------------------------------------
# Plot 6: Break-even analysis
# ---------------------------------------------------------------------------


def plot_break_even(summary: list[dict], plots_dir: Path):
    """Scatter: request rate at which KV-cache memory cost breaks even."""
    import matplotlib.pyplot as plt

    from research.tr123.kv_cache_analysis import (
        MODEL_ARCHITECTURES,
        compute_break_even,
        kv_cache_mb,
    )

    # Derive memory cost from consumer RTX 4080 pricing:
    # $1200 hardware / (3yr * 8760 hr/yr) = $0.046/hr for 12GB VRAM
    # → $0.046 / 12 = $0.00383/GB/hr
    CONSUMER_MEM_COST_PER_GB_HR = 0.046 / 12.0
    CONSUMER_COMPUTE_PER_HR = 0.046

    results = []
    for model_name, arch in MODEL_ARCHITECTURES.items():
        model_rows = [r for r in summary if r.get("model") == model_name]
        if not model_rows:
            continue

        for row in model_rows:
            decode_ms = _safe_float(row.get("decode_ms_mean"))
            if decode_ms is None:
                continue

            # Assume 50% latency savings from KV cache vs uncached
            latency_savings_s = (decode_ms / 1000.0) * 0.5

            for ctx_len in [256, 512, 1024]:
                kv_mb = kv_cache_mb(
                    arch["n_layers"], arch["n_kv_heads"], arch["d_head"], ctx_len
                )
                kv_gb = kv_mb / 1024.0
                be = compute_break_even(
                    kv_gb,
                    CONSUMER_MEM_COST_PER_GB_HR,
                    latency_savings_s,
                    CONSUMER_COMPUTE_PER_HR,
                )
                results.append(
                    {
                        "model": model_name,
                        "backend": row.get("backend", ""),
                        "context_length": ctx_len,
                        "kv_cache_mb": kv_mb,
                        "break_even_req_per_hr": be["break_even_req_per_hr"],
                    }
                )

    if not results:
        logger.warning("No break-even data")
        return

    _fig, ax = plt.subplots(figsize=(10, 6))
    models = sorted({r["model"] for r in results})
    for model in models:
        model_data = [r for r in results if r["model"] == model]
        ctx = [r["context_length"] for r in model_data]
        be = [
            min(r["break_even_req_per_hr"], 100000) for r in model_data
        ]  # Cap for display
        ax.scatter(ctx, be, label=model, alpha=0.6, s=50)

    ax.set_xlabel("Context Length (tokens)")
    ax.set_ylabel("Break-Even Requests/Hour")
    ax.set_title("KV-Cache Break-Even: Requests Needed to Justify Memory")
    ax.legend()
    ax.set_yscale("log")
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(plots_dir / "break_even.png", dpi=150)
    plt.close()
    logger.info("  Saved break_even.png")


# ---------------------------------------------------------------------------
# Plot 7: Latency CDF
# ---------------------------------------------------------------------------


def plot_latency_cdf(results_dir: Path, plots_dir: Path):
    """CDF of prefill and decode latency per backend."""
    import matplotlib.pyplot as plt

    jsonl_path = results_dir / "raw_measurements.jsonl"
    if not jsonl_path.exists():
        return

    from collections import defaultdict

    backend_latencies: dict[str, dict[str, list]] = defaultdict(
        lambda: {"prefill": [], "decode": []}
    )

    with open(jsonl_path, encoding="utf-8") as f:
        for line in f:
            row = json.loads(line.strip())
            if row.get("status") != "ok":
                continue
            b = row.get("backend", "")
            pms = _safe_float(row.get("prefill_ms"))
            dms = _safe_float(row.get("decode_ms"))
            if pms is not None:
                backend_latencies[b]["prefill"].append(pms)
            if dms is not None:
                backend_latencies[b]["decode"].append(dms)

    _fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    for backend in sorted(backend_latencies.keys()):
        # Prefill CDF
        vals = sorted(backend_latencies[backend]["prefill"])
        if vals:
            cdf = np.arange(1, len(vals) + 1) / len(vals)
            ax1.plot(vals, cdf, label=backend)

        # Decode CDF
        vals = sorted(backend_latencies[backend]["decode"])
        if vals:
            cdf = np.arange(1, len(vals) + 1) / len(vals)
            ax2.plot(vals, cdf, label=backend)

    ax1.set_xlabel("Prefill Latency (ms)")
    ax1.set_ylabel("CDF")
    ax1.set_title("Prefill Latency Distribution")
    ax1.legend(fontsize=8)
    ax1.grid(True, alpha=0.3)

    ax2.set_xlabel("Decode Latency (ms)")
    ax2.set_ylabel("CDF")
    ax2.set_title("Decode Latency Distribution")
    ax2.legend(fontsize=8)
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(plots_dir / "latency_cdf.png", dpi=150)
    plt.close()
    logger.info("  Saved latency_cdf.png")


# ---------------------------------------------------------------------------
# Plot 8: Cost tier comparison
# ---------------------------------------------------------------------------


def plot_cost_tier_comparison(results_dir: Path, plots_dir: Path):
    """Grouped bar chart: $/1M tokens across pricing tiers."""
    import matplotlib.pyplot as plt

    tier_path = results_dir / "cost_table_all_tiers.csv"
    if not tier_path.exists():
        logger.warning("No cost_table_all_tiers.csv found")
        return

    data = _load_csv(tier_path)
    tiers = sorted({r.get("pricing_tier", "") for r in data})
    backends = sorted({r.get("backend", "") for r in data})

    # Average production cost per (tier, backend)
    from collections import defaultdict

    tier_backend_cost: dict[tuple, list] = defaultdict(list)
    for r in data:
        cost = _safe_float(r.get("production_cost_per_1m_mean"))
        if cost is not None:
            tier_backend_cost[(r["pricing_tier"], r["backend"])].append(cost)

    _fig, ax = plt.subplots(figsize=(12, 6))
    x = np.arange(len(backends))
    width = 0.8 / max(len(tiers), 1)

    colors = ["#2196F3", "#FF9800", "#4CAF50", "#9C27B0", "#F44336"]
    for i, tier in enumerate(tiers):
        costs = []
        for backend in backends:
            vals = tier_backend_cost.get((tier, backend), [])
            costs.append(np.mean(vals) if vals else 0)
        ax.bar(
            x + i * width - 0.4 + width / 2,
            costs,
            width,
            label=tier,
            color=colors[i % len(colors)],
        )

    ax.set_xlabel("Backend")
    ax.set_ylabel("$/1M tokens (production blend)")
    ax.set_title("Cost per 1M Tokens by Pricing Tier")
    ax.set_xticks(x)
    ax.set_xticklabels(backends, rotation=30, ha="right")
    ax.legend(fontsize=8)
    plt.tight_layout()
    plt.savefig(plots_dir / "cost_tier_comparison.png", dpi=150)
    plt.close()
    logger.info("  Saved cost_tier_comparison.png")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def generate_all_plots(results_dir: str | Path):
    """Generate all 8 plot types."""
    results_dir = Path(results_dir)
    plots_dir = results_dir / "plots"
    _ensure_dir(plots_dir)

    import matplotlib

    matplotlib.use("Agg")

    logger.info(f"Generating plots → {plots_dir}")

    # Load data
    summary_path = results_dir / "summary_stats.csv"
    summary = _load_csv(summary_path) if summary_path.exists() else []

    improvement_path = results_dir / "improvement_ratios.csv"
    improvement = _load_csv(improvement_path) if improvement_path.exists() else []

    # Generate all plots
    models = sorted({r.get("model", "") for r in summary})
    for model in models:
        plot_phase_cost_bar(summary, plots_dir, model)

    if improvement:
        plot_cached_vs_uncached(improvement, plots_dir)

    plot_energy_heatmap(summary, plots_dir)
    plot_kv_memory_scaling(results_dir, plots_dir)
    plot_crossover(results_dir, plots_dir)

    try:
        plot_break_even(summary, plots_dir)
    except Exception as e:
        logger.warning(f"Break-even plot failed: {e}")

    plot_latency_cdf(results_dir, plots_dir)
    plot_cost_tier_comparison(results_dir, plots_dir)

    logger.info("All plots generated.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TR123: Visualization")
    parser.add_argument("results_dir", help="Path to results directory")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    generate_all_plots(args.results_dir)
