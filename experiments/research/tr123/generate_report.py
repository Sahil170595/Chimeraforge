#!/usr/bin/env python3
"""
TR123: Report Generator.

Reads analysis CSVs and generates PublishReady/reports/Technical_Report_123.md.
"""

from __future__ import annotations

import argparse
import csv
from datetime import UTC, datetime
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _load_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _safe_float(v: Any, decimals: int = 4) -> str:
    if v is None or v == "" or v == "None":
        return "N/A"
    try:
        return f"{float(v):.{decimals}f}"
    except (ValueError, TypeError):
        return "N/A"


def _load_manifest(results_dir: Path) -> dict[str, Any]:
    manifest_path = results_dir / "manifest.json"
    if manifest_path.exists():
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    return {}


def generate_report(results_dir: str | Path) -> Path:
    """Generate Technical_Report_123.md from analysis results."""
    results_dir = Path(results_dir)
    repo_root = Path(__file__).resolve().parents[2]
    report_path = repo_root / "PublishReady" / "reports" / "Technical_Report_123.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    manifest = _load_manifest(results_dir)
    summary = _load_csv(results_dir / "summary_stats.csv")
    _load_csv(results_dir / "cost_table_all_tiers.csv")
    improvement = _load_csv(results_dir / "improvement_ratios.csv")
    kv_theoretical = _load_csv(
        results_dir / "kv_cache_analysis" / "kv_memory_theoretical.csv"
    )
    kv_crossover = _load_csv(
        results_dir / "kv_cache_analysis" / "kv_crossover_points.csv"
    )

    lines: list[str] = []

    def w(text: str = ""):
        lines.append(text)

    # Header
    w("# Technical Report 123: KV-Cache Production Economics")
    w()
    w(f"**Date:** {datetime.now(UTC).strftime('%Y-%m-%d')}")
    w("**Status:** Complete")
    w("**Phase:** 2 — KV-Cache Production Economics")
    w("**Hardware:** RTX 4080 Laptop (consumer)")
    w()

    # Abstract
    w("## Abstract")
    w()
    w(
        "TR119 established cost-per-token economics using `use_cache=False` — an intentionally"
    )
    w(
        "pessimistic measurement that ignores KV-cache reuse during autoregressive decode."
    )
    w(
        "This report measures production-grade inference with KV-cache enabled, separating"
    )
    w(
        "prefill (prompt processing) and decode (token generation) into distinct cost phases."
    )
    w("We test across 5 diverse models spanning 124M to 3.2B parameters with both MHA")
    w(
        "(multi-head attention) and GQA (grouped-query attention) architectures, quantifying"
    )
    w("real $/1M tokens for consumer-hardware deployment and analyzing KV-cache memory")
    w("overhead vs. latency benefit. GQA models (Llama-3.2, Qwen2.5) demonstrate")
    w(
        "dramatically smaller KV caches than MHA models (GPT-2, Phi-2) at the same scale."
    )
    w()

    # Methodology
    w("## Methodology")
    w()
    w("### Measurement Protocol")
    w()
    w("Two-phase measurement inspired by TokenPowerBench (Dec 2025) and prefill-decode")
    w("disaggregation literature (SPAD, Nexus, DuetServe 2025):")
    w()
    w("1. **Prefill**: `model(input_ids, use_cache=True)` → captures `past_key_values`")
    w("2. **Decode**: Token-by-token loop with `past_key_values` reuse")
    w("3. **Timing**: CUDA events (GPU-side) + `time.perf_counter()` (wall-clock)")
    w(
        "4. **Power**: PhasePowerSampler tags each NVML sample with active phase (prefill/decode)"
    )
    w("5. **Thermal**: GPU cooldown between model loads, throttle detection at 80°C")
    w("6. **Precision**: FP16 on CUDA (consistent with cost/memory formulas)")
    w("7. **Prompts**: Natural-language corpus (not random word generation)")
    w()

    if manifest:
        w("### Experiment Configuration")
        w()
        w(f"- **Models:** {', '.join(manifest.get('models', []))}")
        w(f"- **Backends:** {', '.join(manifest.get('backends', []))}")
        w(f"- **Scenarios:** {', '.join(manifest.get('scenarios', []))}")
        w(f"- **Repetitions:** {manifest.get('repetitions', 'N/A')}")
        w(f"- **Run ID:** {manifest.get('run_id', 'N/A')}")
        w()

    w("### Model Lineup")
    w()
    w("| Model | Params | Attention | KV Heads | d_head | FP16 VRAM |")
    w("|-------|--------|-----------|----------|--------|-----------|")
    w("| GPT-2 | 124M | MHA | 12 | 64 | 0.3 GB |")
    w("| Llama-3.2-1B | 1.24B | GQA (4:1) | 8 | 64 | 2.5 GB |")
    w("| Qwen2.5-1.5B | 1.54B | GQA (6:1) | 2 | 128 | 3.1 GB |")
    w("| Phi-2 | 2.7B | MHA | 32 | 80 | 5.4 GB |")
    w("| Llama-3.2-3B | 3.21B | GQA (3:1) | 8 | 128 | 6.4 GB |")
    w()

    w("### Cost Model")
    w()
    w("Phase-split cost accounting:")
    w()
    w("```")
    w("prefill_tok/s = prompt_tokens / (prefill_ms / 1000)")
    w("decode_tok/s  = gen_tokens   / (decode_ms / 1000)")
    w("$/1M_prefill  = (1M / prefill_tok/s / 3600) × hourly_rate + energy")
    w("$/1M_decode   = (1M / decode_tok/s  / 3600) × hourly_rate + energy")
    w("$/1M_blend    = 0.67 × $/1M_prefill + 0.33 × $/1M_decode")
    w("```")
    w()
    w("Energy attribution uses per-phase power means (not whole-run average):")
    w(
        "`E_prefill = P_prefill_mean × t_prefill`, `E_decode = P_decode_mean × t_decode`."
    )
    w()
    w("Cost sensitivity computed across 5 workload profiles:")
    w(
        "RAG-heavy (95/5), summarization (85/15), chat (67/33), balanced (50/50), code-gen (25/75)."
    )
    w()

    # Results
    w("## Results")
    w()

    if summary:
        w("### Phase-Split Latency")
        w()
        w(
            "| Model | Backend | Scenario | Prefill (ms) | Decode (ms) | Total (ms) | N |"
        )
        w("|-------|---------|----------|-------------|------------|-----------|---|")
        for r in summary:
            w(
                f"| {r.get('model', '')} | {r.get('backend', '')} | {r.get('scenario', '')} "
                f"| {_safe_float(r.get('prefill_ms_mean'), 1)} "
                f"| {_safe_float(r.get('decode_ms_mean'), 1)} "
                f"| {_safe_float(r.get('total_ms_mean'), 1)} "
                f"| {r.get('n_measurements', '')} |"
            )
        w()

        w("### Phase-Split Cost (Consumer RTX 4080)")
        w()
        w("| Model | Backend | Scenario | $/1M Prefill | $/1M Decode | $/1M Blend |")
        w("|-------|---------|----------|-------------|------------|-----------|")
        for r in summary:
            w(
                f"| {r.get('model', '')} | {r.get('backend', '')} | {r.get('scenario', '')} "
                f"| {_safe_float(r.get('prefill_cost_per_1m_mean'))} "
                f"| {_safe_float(r.get('decode_cost_per_1m_mean'))} "
                f"| {_safe_float(r.get('production_cost_per_1m_mean'))} |"
            )
        w()

    # KV-Cache Memory Analysis
    w("## KV-Cache Memory Analysis")
    w()
    w("### Theoretical Overhead")
    w()
    w("Formula: `KV_bytes = 2 × L × B × T × H_kv × D_h × precision_bytes`")
    w()

    if kv_theoretical:
        w("| Model | Context Length | KV Cache (MB) | Weights (MB) | Cache/Weights |")
        w("|-------|--------------|--------------|-------------|--------------|")
        for r in kv_theoretical:
            w(
                f"| {r.get('model', '')} | {r.get('context_length', '')} "
                f"| {_safe_float(r.get('kv_cache_theoretical_mb'), 2)} "
                f"| {_safe_float(r.get('model_weights_mb'), 1)} "
                f"| {_safe_float(r.get('cache_to_weights_ratio'))} |"
            )
        w()

    if kv_crossover:
        w("### Crossover Points")
        w()
        w("Sequence length where KV-cache memory equals model weight size:")
        w()
        w("| Model | Params (M) | Crossover (tokens) |")
        w("|-------|-----------|-------------------|")
        for r in kv_crossover:
            w(
                f"| {r.get('model', '')} | {r.get('params_m', '')} | {r.get('crossover_tokens', '')} |"
            )
        w()

    # Cross-reference
    if improvement:
        w("## Cross-Reference with TR119 (Uncached)")
        w()
        w("| Model | Backend | Latency Speedup | Cost Reduction |")
        w("|-------|---------|----------------|---------------|")
        for r in improvement:
            w(
                f"| {r.get('model', '')} | {r.get('backend', '')} "
                f"| {_safe_float(r.get('latency_speedup_x'), 1)}x "
                f"| {_safe_float(r.get('cost_reduction_x'), 1)}x |"
            )
        w()

    # Discussion
    w("## Discussion")
    w()
    w("### Key Findings")
    w()
    w(
        "1. **Phase asymmetry**: Prefill (compute-bound) and decode (memory-bandwidth-bound)"
    )
    w("   have fundamentally different cost profiles, validating separate pricing for")
    w("   input vs output tokens as practiced by commercial LLM providers.")
    w()
    w(
        "2. **KV-cache benefit**: Cached decode avoids recomputing attention over the full"
    )
    w("   context, yielding significant latency and cost improvements over TR119's")
    w("   uncached measurements.")
    w()
    w("3. **GQA vs MHA**: Models with grouped-query attention (Llama-3.2, Qwen2.5) use")
    w(
        "   dramatically less KV-cache memory than MHA models (GPT-2, Phi-2). Qwen2.5-1.5B"
    )
    w(
        "   with only 2 KV heads represents an extreme case where cache memory is minimal"
    )
    w("   even at long context lengths.")
    w()
    w("4. **Memory overhead**: KV-cache memory scales linearly with context length.")
    w("   On consumer hardware (12GB VRAM), the crossover point where KV cache exceeds")
    w("   model weights varies dramatically by architecture: GQA models can serve much")
    w("   longer contexts before memory becomes the bottleneck.")
    w()

    w("## References")
    w()
    w("- TR119: Cost & Energy Analysis (Banterhearts)")
    w("- TR121: Comprehensive Scaling Analysis (Banterhearts)")
    w("- TokenPowerBench (arXiv:2512.03024, Dec 2025)")
    w("- SPAD: Specialized Prefill and Decode Hardware (2025)")
    w("- Brenndoerfer: KV Cache Memory Calculation (2025)")
    w("- Keep the Cost Down: KV-Cache Optimization Survey (arXiv:2407.18003)")
    w()
    w("---")
    w()
    w("**End of Technical Report 123**")
    w()

    report_text = "\n".join(lines)
    report_path.write_text(report_text, encoding="utf-8")
    logger.info(f"Report written to {report_path} ({len(lines)} lines)")
    return report_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TR123: Report Generator")
    parser.add_argument("results_dir", help="Path to results directory")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    generate_report(args.results_dir)
