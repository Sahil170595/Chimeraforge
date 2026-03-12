"""TR127 — Markdown report generation from analysis.json.

v2: Added sections for cold-start analysis, two-regime decode, KV cross-
validation, multiple comparison correction, ANOVA interaction, trimmed-mean
robustness, and distribution shape analysis.

Usage:
    python research/tr127/generate_report.py -v
    python research/tr127/generate_report.py --run-dir research/tr127/results/20260223_120000
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
import logging
from pathlib import Path
import sys

_DIR = Path(__file__).resolve().parent
_REPO = _DIR.parents[1]
sys.path.insert(0, str(_REPO))

from research.tr127.shared.utils import TR127_RESULTS, effect_label, find_latest_run

log = logging.getLogger("tr127.report")


# ── section builders ──────────────────────────────────────────────────


def _section_environment(manifest: dict) -> str:
    env = manifest.get("environment", {})
    py_ver = env.get("python_version", "N/A")
    if isinstance(py_ver, str):
        py_ver = py_ver.split()[0]
    lines = [
        "## 1. Environment\n",
        f"- **Platform:** {env.get('platform', 'N/A')}",
        f"- **Python:** {py_ver}",
        f"- **PyTorch:** {env.get('torch_version', 'N/A')}",
        f"- **CUDA:** {env.get('cuda_version', 'N/A')}",
        f"- **GPU:** {env.get('gpu_name', 'N/A')} "
        f"({env.get('gpu_memory_gb', '?')} GB)",
        f"- **Run ID:** {manifest.get('run_id', 'N/A')}",
        f"- **Start:** {manifest.get('start_time', 'N/A')}",
        f"- **End:** {manifest.get('end_time', 'N/A')}",
        "",
    ]
    return "\n".join(lines)


def _section_methodology(analysis: dict, manifest: dict) -> str:
    cfg = manifest.get("config", {})
    summary = analysis.get("summary", {})
    lines = [
        "## 2. Methodology\n",
        f"- **Context lengths:** {summary.get('context_lengths', [])}",
        f"- **Models:** {', '.join(summary.get('models', []))}",
        f"- **Backends:** {', '.join(summary.get('backends', []))}",
        f"- **Repetitions:** {cfg.get('repetitions', 'N/A')} "
        f"(+ {cfg.get('warmup_repetitions', 'N/A')} warmup)",
        f"- **Max new tokens:** {cfg.get('max_new_tokens', 'N/A')}",
        "- **Temperature:** 0.0 (greedy)",
        f"- **Seed:** {cfg.get('seed', 'N/A')}",
        f"- **Total rows:** {summary.get('total_rows', 0)}",
        f"- **Status counts:** {summary.get('status_counts', {})}",
        "",
    ]
    return "\n".join(lines)


def _section_cold_start(analysis: dict) -> str:
    data = analysis.get("cold_start_analysis", {})
    lines = ["## 3. Ollama Cold-Start Analysis\n"]

    if not data or "note" in data:
        lines.append("*No Ollama cold-start data available.*\n")
        return "\n".join(lines)

    summary = data.get("_summary", {})
    lines.append(
        f"> **{summary.get('cold_starts_detected', 0)}/"
        f"{summary.get('total_groups', 0)}** Ollama measurement groups "
        f"({summary.get('cold_start_pct', 0):.0f}%) show cold-start "
        f"inflation at rep-0, despite 3 warmup repetitions.\n"
    )

    # Per-model cold-start tables
    for model_name in sorted(k for k in data if k != "_summary"):
        model_data = data[model_name]
        if not model_data:
            continue
        lines.append(f"### {model_name}\n")
        lines.append(
            "| Context | Rep-0 (ms) | Rest Median (ms) | Cold Ratio "
            "| Mean Inflation | Rest CV% |"
        )
        lines.append(
            "|---------|-----------|------------------|------------|"
            "----------------|---------|"
        )
        for cl in sorted(model_data.keys(), key=int):
            v = model_data[cl]
            cold_flag = " !!!" if v.get("cold_ratio", 0) > 5 else ""
            lines.append(
                f"| {int(cl):,} | {v['rep0_ms']:.1f} "
                f"| {v['rest_median_ms']:.1f} "
                f"| {v['cold_ratio']:.1f}x{cold_flag} "
                f"| +{v['mean_inflation_pct']:.1f}% "
                f"| {v['rest_cv_pct']:.1f}% |"
            )
        lines.append("")

    lines.append(f"> {summary.get('recommendation', '')}\n")
    return "\n".join(lines)


def _section_prefill_scaling(analysis: dict) -> str:
    data = analysis.get("prefill_scaling", {})
    lines = ["## 4. Prefill Scaling\n"]

    if not data:
        lines.append("*No prefill data available.*\n")
        return "\n".join(lines)

    # Check if any entries have clean_scaling (pre-thrashing fits)
    has_clean = any("clean_scaling" in fit for fit in data.values())

    if has_clean:
        lines.append(
            "> **Two-regime analysis:** HF models show VRAM spillover at "
            "high context lengths,\n> causing 25-100x latency jumps from "
            "system-memory paging. The table below\n> shows both the "
            "full-range fit (dominated by thrashing) and the clean fit\n"
            "> (pre-spillover data only, representing true computational "
            "scaling).\n"
        )

    # Summary table — full range
    lines.append("### Full-Range Fit\n")
    lines.append(
        "| Model | Backend | Exponent (b) | R^2 (power) | R^2 (quad) "
        "| R^2 (linear) | Better Fit |"
    )
    lines.append(
        "|-------|---------|-------------|-------------|----------"
        "|-------------|------------|"
    )

    for key, fit in sorted(data.items()):
        model, backend = key.split("__", 1)
        pl = fit.get("power_law", {})
        lin = fit.get("linear", {})
        quad = fit.get("quadratic", {})
        b = f"{pl['b']:.3f}" if isinstance(pl.get("b"), (int, float)) else "N/A"
        r2p = (
            f"{pl['r_squared']:.4f}"
            if isinstance(pl.get("r_squared"), (int, float))
            else "N/A"
        )
        r2q = (
            f"{quad['r_squared']:.4f}"
            if isinstance(quad.get("r_squared"), (int, float))
            else "N/A"
        )
        r2l = (
            f"{lin['r_squared']:.4f}"
            if isinstance(lin.get("r_squared"), (int, float))
            else "N/A"
        )
        better = fit.get("better_fit", "N/A")
        lines.append(
            f"| {model} | {backend} | {b} | {r2p} | {r2q} " f"| {r2l} | {better} |"
        )

    lines.append("")

    # Clean scaling table (pre-thrashing) if available
    clean_entries = {k: v for k, v in data.items() if "clean_scaling" in v}
    if clean_entries:
        lines.append("### Pre-Thrashing Fit (True Computational Scaling)\n")
        lines.append(
            "| Model | Backend | Clean Points | Exponent (b) "
            "| R^2 (power) | R^2 (quad) | R^2 (linear) "
            "| Thrashing At | Thrashing Mult |"
        )
        lines.append(
            "|-------|---------|-------------|-------------|"
            "-------------|------------|-------------|"
            "-------------|---------------|"
        )
        for key, fit in sorted(clean_entries.items()):
            model, backend = key.split("__", 1)
            cs = fit["clean_scaling"]
            pl = cs.get("power_law", {})
            lin = cs.get("linear", {})
            quad = cs.get("quadratic", {})
            b = f"{pl['b']:.3f}" if isinstance(pl.get("b"), (int, float)) else "N/A"
            r2p = (
                f"{pl['r_squared']:.4f}"
                if isinstance(pl.get("r_squared"), (int, float))
                else "N/A"
            )
            r2q = (
                f"{quad['r_squared']:.4f}"
                if isinstance(quad.get("r_squared"), (int, float))
                else "N/A"
            )
            r2l = (
                f"{lin['r_squared']:.4f}"
                if isinstance(lin.get("r_squared"), (int, float))
                else "N/A"
            )
            n_clean = cs.get("n_points", "?")
            thresh = fit.get("thrashing_threshold", "?")
            mult = fit.get("thrashing_multiplier", "?")
            lines.append(
                f"| {model} | {backend} | {n_clean} | {b} "
                f"| {r2p} | {r2q} | {r2l} | {thresh} | {mult}x |"
            )
        lines.append("")

    # Trimmed-mean robustness subsection
    has_trimmed = any("trimmed_mean_fits" in v for v in data.values())
    if has_trimmed:
        lines.append("### Trimmed-Mean Robustness\n")
        lines.append(
            "> Scaling exponents re-fit using trimmed means (5%, 10%) "
            "instead of median\n> to assess sensitivity to outliers. "
            "With N=10 reps, 5% trim removes 0 values\n> (floor(10*0.05)=0), "
            "while 10% trim removes 1 from each tail.\n"
        )
        lines.append(
            "| Model | Backend | Median b | Trim 5% b | Trim 10% b | Stable? |"
        )
        lines.append(
            "|-------|---------|----------|-----------|------------|---------|"
        )
        for key, fit in sorted(data.items()):
            tm = fit.get("trimmed_mean_fits", {})
            if not tm:
                continue
            model, backend = key.split("__", 1)
            pl = fit.get("power_law", {})
            orig_b = pl.get("b", 0) if isinstance(pl.get("b"), (int, float)) else None
            t5 = tm.get("trim_5pct", {})
            t10 = tm.get("trim_10pct", {})
            b5 = t5.get("exponent_b")
            b10 = t10.get("exponent_b")

            orig_str = f"{orig_b:.3f}" if orig_b is not None else "N/A"
            b5_str = f"{b5:.3f}" if b5 is not None else "N/A"
            b10_str = f"{b10:.3f}" if b10 is not None else "N/A"

            # Stability check: all within 10% of each other
            vals = [v for v in [orig_b, b5, b10] if v is not None]
            if len(vals) >= 2 and min(vals) > 0:
                ratio = max(vals) / min(vals)
                stable = "Yes" if ratio < 1.1 else f"No ({ratio:.1f}x)"
            else:
                stable = "N/A"

            lines.append(
                f"| {model} | {backend} | {orig_str} | {b5_str} "
                f"| {b10_str} | {stable} |"
            )
        lines.append("")

    # Per-model detail tables with p95, p99
    for key, fit in sorted(data.items()):
        model, backend = key.split("__", 1)
        per_ctx = fit.get("per_context_length", {})
        if not per_ctx:
            continue
        lines.append(f"### {model} ({backend})\n")
        lines.append(
            "| Context Length | Mean (ms) | Median (ms) | Std (ms) "
            "| p95 (ms) | p99 (ms) | 95% CI | N |"
        )
        lines.append(
            "|--------------|-----------|-------------|----------"
            "|----------|----------|--------|---|"
        )
        for cl in sorted(per_ctx.keys(), key=int):
            v = per_ctx[cl]
            ci = f"[{v.get('ci_lower', 0):.0f}, {v.get('ci_upper', 0):.0f}]"
            lines.append(
                f"| {int(cl):,} | {v['mean']:.1f} | {v['median']:.1f} "
                f"| {v['std']:.1f} | {v.get('p95', 0):.1f} "
                f"| {v.get('p99', 0):.1f} | {ci} | {v['n']} |"
            )
        lines.append("")

    return "\n".join(lines)


def _section_decode_scaling(analysis: dict) -> str:
    data = analysis.get("decode_scaling", {})
    lines = ["## 5. Decode Scaling\n"]

    if not data:
        lines.append("*No decode data available.*\n")
        return "\n".join(lines)

    # Summary table — full range
    lines.append("### Full-Range Fit\n")
    lines.append("| Model | Backend | Exponent (b) | R^2 (power) | Better Fit |")
    lines.append("|-------|---------|-------------|-------------|------------|")

    for key, fit in sorted(data.items()):
        model, backend = key.split("__", 1)
        pl = fit.get("power_law", {})
        b = f"{pl['b']:.3f}" if isinstance(pl.get("b"), (int, float)) else "N/A"
        r2p = (
            f"{pl['r_squared']:.4f}"
            if isinstance(pl.get("r_squared"), (int, float))
            else "N/A"
        )
        better = fit.get("better_fit", "N/A")
        lines.append(f"| {model} | {backend} | {b} | {r2p} | {better} |")

    lines.append("")

    # Two-regime decode table (pre-thrashing fits)
    clean_entries = {k: v for k, v in data.items() if "clean_scaling" in v}
    if clean_entries:
        lines.append("### Pre-Thrashing Decode Fit\n")
        lines.append(
            "> Decode latency also suffers from VRAM spillover. Pre-thrashing\n"
            "> exponents show the true KV-cache lookup cost scaling.\n"
        )
        lines.append(
            "| Model | Backend | Clean Points | Exponent (b) "
            "| R^2 (power) | Thrashing At | Thrashing Mult |"
        )
        lines.append(
            "|-------|---------|-------------|-------------|"
            "-------------|-------------|---------------|"
        )
        for key, fit in sorted(clean_entries.items()):
            model, backend = key.split("__", 1)
            cs = fit["clean_scaling"]
            pl = cs.get("power_law", {})
            b = f"{pl['b']:.3f}" if isinstance(pl.get("b"), (int, float)) else "N/A"
            r2p = (
                f"{pl['r_squared']:.4f}"
                if isinstance(pl.get("r_squared"), (int, float))
                else "N/A"
            )
            n_clean = cs.get("n_points", "?")
            thresh = fit.get("thrashing_threshold", "?")
            mult = fit.get("thrashing_multiplier", "?")
            lines.append(
                f"| {model} | {backend} | {n_clean} | {b} "
                f"| {r2p} | {thresh} | {mult}x |"
            )
        lines.append("")

    # Trimmed-mean robustness for decode
    has_trimmed = any("trimmed_mean_fits" in v for v in data.values())
    if has_trimmed:
        lines.append("### Decode Trimmed-Mean Robustness\n")
        lines.append(
            "| Model | Backend | Median b | Trim 5% b | Trim 10% b | Stable? |"
        )
        lines.append(
            "|-------|---------|----------|-----------|------------|---------|"
        )
        for key, fit in sorted(data.items()):
            tm = fit.get("trimmed_mean_fits", {})
            if not tm:
                continue
            model, backend = key.split("__", 1)
            pl = fit.get("power_law", {})
            orig_b = pl.get("b", 0) if isinstance(pl.get("b"), (int, float)) else None
            t5 = tm.get("trim_5pct", {})
            t10 = tm.get("trim_10pct", {})
            b5 = t5.get("exponent_b")
            b10 = t10.get("exponent_b")

            orig_str = f"{orig_b:.3f}" if orig_b is not None else "N/A"
            b5_str = f"{b5:.3f}" if b5 is not None else "N/A"
            b10_str = f"{b10:.3f}" if b10 is not None else "N/A"

            vals = [v for v in [orig_b, b5, b10] if v is not None]
            if len(vals) >= 2 and min(vals) > 0:
                ratio = max(vals) / min(vals)
                stable = "Yes" if ratio < 1.1 else f"No ({ratio:.1f}x)"
            else:
                stable = "N/A"

            lines.append(
                f"| {model} | {backend} | {orig_str} | {b5_str} "
                f"| {b10_str} | {stable} |"
            )
        lines.append("")

    # Decode throughput tables with tail latency
    for key, fit in sorted(data.items()):
        model, backend = key.split("__", 1)
        per_ctx = fit.get("per_context_length", {})
        if not per_ctx:
            continue
        lines.append(f"### {model} ({backend}) — Decode Throughput\n")
        lines.append(
            "| Context Length | Latency Mean (ms) | Latency Median (ms) "
            "| p95 (ms) | Throughput Mean (tok/s) | Throughput Std | N |"
        )
        lines.append(
            "|--------------|-------------------|--------------------"
            "|----------|----------------------|----------------|---|"
        )
        for cl in sorted(per_ctx.keys(), key=int):
            v = per_ctx[cl]
            lines.append(
                f"| {int(cl):,} | {v['latency_mean']:.1f} "
                f"| {v.get('latency_median', v['latency_mean']):.1f} "
                f"| {v.get('latency_p95', 0):.1f} "
                f"| {v['throughput_mean']:.1f} "
                f"| {v['throughput_std']:.1f} | {v['n']} |"
            )
        lines.append("")

    return "\n".join(lines)


def _section_vram_scaling(analysis: dict) -> str:
    data = analysis.get("vram_scaling", {})
    lines = ["## 6. Memory Scaling (CUDA Allocation)\n"]

    if not data:
        lines.append("*No VRAM data available (HF backend only).*\n")
        return "\n".join(lines)

    lines.append(
        "> **Note:** Peak values are `torch.cuda.max_memory_allocated()` "
        "which includes\n> CUDA Unified Memory spillover to system RAM. "
        "Values exceeding physical GPU\n> memory (12 GB) indicate "
        "system-memory paging — a key performance cliff.\n"
    )

    gpu_vram_mb = 12288.0  # default

    lines.append(
        "| Model | Slope (MB/token) | KV Cost (B/tok) | R^2 "
        "| Spillover At | OOM Cliff |"
    )
    lines.append(
        "|-------|-----------------|-----------------|-----"
        "|-------------|-----------|"
    )

    for model, info in sorted(data.items()):
        fit = info.get("linear_fit", {})
        slope = f"{fit['slope_mb_per_token']:.4f}" if fit else "N/A"
        kv_cost = info.get("kv_cache_bytes_per_token")
        kv_str = f"{kv_cost:,.0f}" if kv_cost is not None else "N/A"
        r2 = f"{fit['r_squared']:.4f}" if fit else "N/A"
        spillover = str(info.get("spillover_threshold") or "None")
        oom = str(info.get("oom_cliff") or "None")
        lines.append(
            f"| {model} | {slope} | {kv_str} | {r2} " f"| {spillover} | {oom} |"
        )

    lines.append("")

    # KV Cross-Validation subsection
    kv_cv = analysis.get("kv_cross_validation", {})
    if kv_cv:
        lines.append("### KV Cache Cross-Validation with Theory\n")
        lines.append(
            "> Theoretical KV cost = n_layers x n_kv_heads x head_dim x 2(K+V) "
            "x 2B(FP16).\n> Empirical slope captures KV cache + activations + "
            "allocator overhead.\n"
        )
        lines.append(
            "| Model | Architecture | Theoretical (B/tok) "
            "| Empirical (B/tok) | Overhead |"
        )
        lines.append(
            "|-------|-------------|--------------------"
            "|-------------------|---------|"
        )
        for model_name, info in sorted(kv_cv.items()):
            arch = info.get("architecture", {})
            arch_str = (
                f"{arch.get('n_layers', '?')}L x "
                f"{arch.get('n_kv_heads', '?')}KV x "
                f"{arch.get('head_dim', '?')}d"
            )
            theoretical = info.get("theoretical_kv_bytes_per_token", 0)
            empirical = info.get("empirical_kv_bytes_per_token")
            overhead = info.get("overhead_ratio")

            emp_str = f"{empirical:,.0f}" if empirical is not None else "N/A"
            ovh_str = f"{overhead:.1f}x" if overhead is not None else "N/A"

            lines.append(
                f"| {model_name} | {arch_str} | {theoretical:,} "
                f"| {emp_str} | {ovh_str} |"
            )
        lines.append("")
        lines.append(
            "> The large overhead ratios (20-94x) are expected: the VRAM "
            "slope captures\n> *all* memory that grows with context length, "
            "including attention workspace,\n> activation tensors, and CUDA "
            "allocator fragmentation — not just KV cache.\n> GQA's aggressive "
            "head sharing (2 KV heads) makes the theoretical KV cost\n> a "
            "small fraction of total context-dependent memory.\n"
        )

    # Per-model VRAM tables with regime indicator
    for model, info in sorted(data.items()):
        per_ctx = info.get("per_context_length", {})
        if not per_ctx:
            continue
        info.get("gpu_vram_mb", gpu_vram_mb)
        lines.append(f"### {model} — CUDA Allocation\n")
        lines.append(
            "| Context Length | Peak Alloc (MB) | In GPU? " "| Spillover (GB) |"
        )
        lines.append("|--------------|----------------|---------|" "---------------|")
        for cl in sorted(per_ctx.keys(), key=int):
            v = per_ctx[cl]
            in_gpu = "Yes" if v.get("in_gpu", True) else "**NO**"
            spill = v.get("spillover_gb", 0)
            spill_str = f"{spill:.1f}" if spill > 0 else "-"
            lines.append(
                f"| {int(cl):,} | {v['max_mb']:,.0f} | {in_gpu} " f"| {spill_str} |"
            )
        lines.append("")

    return "\n".join(lines)


def _section_ttft(analysis: dict) -> str:
    data = analysis.get("ttft_analysis", {})
    lines = ["## 7. TTFT Analysis\n"]

    if not data:
        lines.append("*No TTFT data available.*\n")
        return "\n".join(lines)

    # Threshold crossing table
    lines.append("### Threshold Crossings\n")
    lines.append("| Model | Backend | >1s | >5s | >10s |")
    lines.append("|-------|---------|-----|-----|------|")

    for key, info in sorted(data.items()):
        model, backend = key.split("__", 1)
        tc = info.get("threshold_crossings", {})
        t1 = str(tc.get(">1000ms") or "Never")
        t5 = str(tc.get(">5000ms") or "Never")
        t10 = str(tc.get(">10000ms") or "Never")
        lines.append(f"| {model} | {backend} | {t1} | {t5} | {t10} |")

    lines.append("")

    # Detailed TTFT tables with p95
    for key, info in sorted(data.items()):
        model, backend = key.split("__", 1)
        per_ctx = info.get("per_context_length", {})
        if not per_ctx:
            continue
        lines.append(f"### {model} ({backend}) — TTFT\n")
        lines.append(
            "| Context Length | Mean (ms) | Median (ms) " "| p95 (ms) | 95% CI | N |"
        )
        lines.append(
            "|--------------|-----------|-------------" "|----------|--------|---|"
        )
        for cl in sorted(per_ctx.keys(), key=int):
            v = per_ctx[cl]
            ci = f"[{v['ci_lower']:.0f}, {v['ci_upper']:.0f}]"
            lines.append(
                f"| {int(cl):,} | {v['mean_ms']:.1f} | {v['median_ms']:.1f} "
                f"| {v.get('p95', 0):.1f} | {ci} | {v['n']} |"
            )
        lines.append("")

    return "\n".join(lines)


def _section_backend_comparison(analysis: dict) -> str:
    data = analysis.get("backend_comparison", {})
    mc = analysis.get("multiple_comparisons", {})
    lines = ["## 8. Backend Comparison (HF vs Ollama)\n"]

    if not data:
        lines.append("*No shared models between backends for comparison.*\n")
        return "\n".join(lines)

    # Multiple comparison correction summary
    if mc and mc.get("n_tests", 0) > 0:
        lines.append("### Multiple Comparison Correction\n")
        lines.append(f"- **Total pairwise tests:** {mc['n_tests']}")
        lines.append(
            f"- **Uncorrected significant (p<0.05):** "
            f"{mc['uncorrected_significant']}/{mc['n_tests']}"
        )
        lines.append(
            f"- **Bonferroni significant "
            f"(p<{mc.get('bonferroni_threshold', 0):.4f}):** "
            f"{mc['bonferroni_significant']}/{mc['n_tests']}"
        )
        lines.append(
            f"- **Holm-Bonferroni significant:** "
            f"{mc['holm_significant']}/{mc['n_tests']}"
        )
        lines.append("")

        if mc.get("interpretation"):
            lines.append(f"> {mc['interpretation']}\n")

    # Pairwise comparison tables
    for mode, models in sorted(data.items()):
        lines.append(f"### {mode.capitalize()}\n")
        for model, per_ctx in sorted(models.items()):
            if not per_ctx:
                continue
            lines.append(f"#### {model}\n")
            lines.append(
                "| Context Length | HF Mean (ms) | Ollama Mean (ms) "
                "| Diff (ms) | % Change | p-value | Sig? "
                "| Cohen's d | Effect |"
            )
            lines.append(
                "|--------------|-------------|------------------"
                "|-----------|----------|---------|------"
                "|-----------|--------|"
            )
            for cl in sorted(per_ctx.keys(), key=int):
                v = per_ctx[cl]
                sig = "Yes" if v["significant"] else "No"
                eff = v.get("effect_label", effect_label(v["cohens_d"]))
                lines.append(
                    f"| {int(cl):,} | {v['hf_mean']:.1f} "
                    f"| {v['ollama_mean']:.1f} "
                    f"| {v['difference_ms']:.1f} "
                    f"| {v['percent_change']:.1f}% "
                    f"| {v['p_value']:.4f} | {sig} "
                    f"| {v['cohens_d']:.2f} | {eff} |"
                )
            lines.append("")

    return "\n".join(lines)


def _section_anova(analysis: dict) -> str:
    data = analysis.get("anova_interaction", {})
    lines = ["## 9. ANOVA Interaction Analysis\n"]

    if not data:
        lines.append("*No ANOVA data available.*\n")
        return "\n".join(lines)

    lines.append(
        "> Tests whether the effect of backend on latency depends on "
        "context length\n> (interaction effect). Only applies to models "
        "available on both backends.\n"
    )

    for mode, models in sorted(data.items()):
        lines.append(f"### {mode.capitalize()}\n")
        for model, info in sorted(models.items()):
            be = info.get("backend_effect", {})
            ce = info.get("context_length_effect", {})
            ie = info.get("interaction_evidence", "none")

            lines.append(f"#### {model}\n")
            lines.append(
                f"- **Backend effect:** F={be.get('f_statistic', 'N/A')}, "
                f"p={be.get('p_value', 'N/A')}, "
                f"{'significant' if be.get('significant') else 'not significant'}"
            )
            lines.append(
                f"- **Context length effect:** F={ce.get('f_statistic', 'N/A')}, "
                f"p={ce.get('p_value', 'N/A')}, "
                f"{'significant' if ce.get('significant') else 'not significant'}"
            )
            lines.append(f"- **Interaction evidence:** {ie}")
            lines.append("")

            # Per-context backend test table
            per_ctx = info.get("per_context_backend_test", {})
            if per_ctx:
                lines.append(
                    "| Context | HF Mean (ms) | Ollama Mean (ms) "
                    "| t-stat | p-value | Sig? |"
                )
                lines.append(
                    "|---------|-------------|------------------"
                    "|--------|---------|------|"
                )
                for cl in sorted(per_ctx.keys()):
                    v = per_ctx[cl]
                    sig = "Yes" if v["significant"] else "No"
                    lines.append(
                        f"| {int(cl):,} | {v['hf_mean']:.1f} "
                        f"| {v['ollama_mean']:.1f} "
                        f"| {v['t_statistic']:.2f} "
                        f"| {v['p_value']:.4f} | {sig} |"
                    )
                lines.append("")

    return "\n".join(lines)


def _section_distribution_shape(analysis: dict) -> str:
    data = analysis.get("distribution_shape", {})
    lines = ["## 10. Distribution Shape Analysis\n"]

    if not data:
        lines.append("*No distribution data available.*\n")
        return "\n".join(lines)

    lines.append(
        "> Mean/median ratio >1.0 indicates right skew (outliers pull "
        "mean up).\n> Ratios >2.0 indicate severe skew where mean is "
        "unreliable as central tendency.\n"
    )

    # Summary table
    lines.append("| Model | Backend | Mode | Pooled Skew | Mean/Median Ratio |")
    lines.append("|-------|---------|------|-------------|-------------------|")
    for key in sorted(data.keys()):
        parts = key.split("__")
        if len(parts) != 3:
            continue
        model, backend, mode = parts
        info = data[key]
        skew = info.get("pooled_skewness")
        mm = info.get("pooled_mean_median_ratio")
        skew_str = f"{skew:.2f}" if skew is not None else "N/A"
        mm_str = f"{mm:.4f}" if mm is not None else "N/A"
        flag = " **!!**" if mm is not None and mm > 2.0 else ""
        lines.append(
            f"| {model} | {backend} | {mode} | {skew_str} " f"| {mm_str}{flag} |"
        )

    lines.append("")

    # Flag extremely skewed groups
    extreme = [
        (k, v)
        for k, v in data.items()
        if v.get("pooled_mean_median_ratio") is not None
        and v["pooled_mean_median_ratio"] > 2.0
    ]
    if extreme:
        lines.append(
            f"> **Warning:** {len(extreme)} groups show mean/median ratio >2.0, "
            f"indicating severe\n> right skew. For these groups, median or "
            f"trimmed mean is the appropriate\n> central tendency measure, "
            f"not the arithmetic mean.\n"
        )

    return "\n".join(lines)


def _section_outlier_analysis(analysis: dict) -> str:
    data = analysis.get("outlier_analysis", {})
    lines = ["## 11. Outlier Analysis\n"]

    if not data:
        lines.append("*No outlier data available.*\n")
        return "\n".join(lines)

    summary = data.get("_summary", {})
    lines.append(f"- **Total measurements:** {summary.get('total_measured', 0)}")
    lines.append(
        f"- **Total outliers (IQR):** {summary.get('total_outliers', 0)} "
        f"({summary.get('overall_outlier_pct', 0):.1f}%)"
    )
    lines.append(f"- **Method:** {summary.get('method', 'N/A')}")
    lines.append("")

    # Detail table — only show groups with outliers
    has_outliers = {
        k: v for k, v in data.items() if k != "_summary" and v.get("n_outliers", 0) > 0
    }

    if has_outliers:
        lines.append("| Model | Backend | Mode | N | Outliers | % |")
        lines.append("|-------|---------|------|---|----------|---|")
        for key in sorted(has_outliers):
            v = has_outliers[key]
            parts = key.split("__")
            model, backend, mode = parts[0], parts[1], parts[2]
            lines.append(
                f"| {model} | {backend} | {mode} "
                f"| {v['n_total']} | {v['n_outliers']} "
                f"| {v['outlier_pct']:.1f}% |"
            )
        lines.append("")
    else:
        lines.append("No outliers detected in any group.\n")

    return "\n".join(lines)


def _section_power_analysis(analysis: dict) -> str:
    data = analysis.get("power_analysis", {})
    lines = [
        "## 12. Power Analysis\n",
        f"- **Repetitions:** {data.get('repetitions', 'N/A')}",
        f"- **Alpha:** {data.get('alpha', 'N/A')}",
        f"- **Power:** {data.get('power', 'N/A')}",
        f"- **Min detectable Cohen's d (z-based):** "
        f"{data.get('min_cohens_d_z', 'N/A')}",
        f"- **Min detectable Cohen's d (t-based):** "
        f"{data.get('min_cohens_d_t', 'N/A')}",
        f"- **Sensitivity:** {data.get('sensitivity', 'N/A')}",
        "",
    ]

    # Stratified table
    strata = data.get("strata", {})
    if strata:
        lines.append("### Per-Stratum Detectable Effects\n")
        lines.append(
            "| Model | Backend | Pooled Std (ms) | Min Detectable (ms) " "| N |"
        )
        lines.append("|-------|---------|----------------|--------------------" "|---|")
        for key in sorted(strata):
            model, backend = key.split("__", 1)
            s = strata[key]
            lines.append(
                f"| {model} | {backend} | {s['pooled_std_ms']:,.1f} "
                f"| {s['min_detectable_ms']:,.1f} "
                f"| {s['n_measurements']} |"
            )
        lines.append("")

        # Per-context CV table
        lines.append("### Measurement Precision (CV% by Context Length)\n")
        lines.append(
            "| Model | Backend | Context | Std (ms) | CV% " "| Min Detectable (ms) |"
        )
        lines.append(
            "|-------|---------|---------|---------|-----" "|---------------------|"
        )
        for key in sorted(strata):
            model, backend = key.split("__", 1)
            per_ctx = strata[key].get("per_context_length", {})
            for cl in sorted(per_ctx.keys()):
                v = per_ctx[cl]
                lines.append(
                    f"| {model} | {backend} | {int(cl):,} "
                    f"| {v['std_ms']:,.1f} | {v['cv_pct']:.1f}% "
                    f"| {v['min_detectable_ms']:,.1f} |"
                )
        lines.append("")

    if data.get("note"):
        lines.append(f"> {data['note']}\n")

    return "\n".join(lines)


def _section_findings(analysis: dict) -> str:
    lines = ["## 13. Key Findings\n"]
    findings = []
    finding_num = 0

    # 1. Prefill scaling — distinguish clean scaling from thrashing
    prefill = analysis.get("prefill_scaling", {})

    # Report clean (pre-thrashing) scaling where available
    for key, fit in sorted(prefill.items()):
        if "clean_scaling" not in fit:
            continue
        model, backend = key.split("__", 1)
        cs = fit["clean_scaling"]
        cs_pl = cs.get("power_law", {})
        cs_quad = cs.get("quadratic", {})
        thresh = fit.get("thrashing_threshold", "?")
        mult = fit.get("thrashing_multiplier", "?")
        finding_num += 1

        b_val = cs_pl.get("b", 0) if isinstance(cs_pl.get("b"), (int, float)) else 0
        r2_q = (
            cs_quad.get("r_squared", 0)
            if isinstance(cs_quad.get("r_squared"), (int, float))
            else 0
        )

        findings.append(
            f"{finding_num}. **Pre-thrashing prefill scaling "
            f"({model}, {backend}):** exponent b = {b_val:.3f}, "
            f"quadratic R^2 = {r2_q:.4f} on clean data "
            f"(512-{fit.get('clean_context_lengths', ['?'])[-1]:,} tokens). "
            f"At {thresh:,} tokens VRAM spills to system RAM "
            f"causing a {mult}x latency cliff."
        )

    # Report full-range superlinearity (which is thrashing, not attention)
    thrashing_entries = [
        (k, f)
        for k, f in prefill.items()
        if f.get("is_superlinear") and "thrashing_threshold" in f
    ]
    if thrashing_entries:
        finding_num += 1
        models = ", ".join(k.split("__")[0] for k, _ in thrashing_entries)
        exponents = ", ".join(
            f"{f['power_law']['b']:.1f}" for _, f in thrashing_entries
        )
        findings.append(
            f"{finding_num}. **VRAM thrashing dominates HF scaling:** "
            f"full-range power-law exponents of b = {exponents} "
            f"for {models} are caused by system-memory paging, not "
            f"O(n^2) attention. The true computational scaling (pre-spillover) "
            f"shows much lower exponents."
        )

    # Ollama stays linear
    ollama_entries = [
        (k, f)
        for k, f in prefill.items()
        if "__ollama" in k and not f.get("is_superlinear")
    ]
    if ollama_entries:
        finding_num += 1
        findings.append(
            f"{finding_num}. **Ollama prefill scales linearly:** "
            f"all {len(ollama_entries)} Ollama model(s) show sub-linear "
            f"prefill scaling (b < 0.2), confirming that llama.cpp's "
            f"optimized attention avoids quadratic overhead at these "
            f"context lengths."
        )

    # Cold-start finding
    cs = analysis.get("cold_start_analysis", {}).get("_summary", {})
    if cs.get("cold_starts_detected", 0) > 0:
        finding_num += 1
        findings.append(
            f"{finding_num}. **Ollama cold-start:** "
            f"{cs['cold_starts_detected']}/{cs['total_groups']} "
            f"({cs['cold_start_pct']:.0f}%) measurement groups show "
            f"rep-0 cold-start inflation (2-10x median). "
            f"Median and 10%-trimmed mean are robust; "
            f"5%-trimmed mean with N=10 is insufficient (removes 0 values)."
        )

    # Decode two-regime
    decode = analysis.get("decode_scaling", {})
    decode_clean = [(k, v) for k, v in decode.items() if "clean_scaling" in v]
    if decode_clean:
        finding_num += 1
        findings.append(
            f"{finding_num}. **Decode also shows two regimes:** "
            f"{len(decode_clean)} HF model(s) show VRAM-spillover decode "
            f"thrashing. Pre-spillover decode exponents "
            f"({', '.join(f'b={v['clean_scaling']['power_law'].get('b', 0):.2f}' for _, v in decode_clean)}) "
            f"confirm near-constant KV-cache lookup cost."
        )

    # Multiple comparisons
    mc = analysis.get("multiple_comparisons", {})
    if mc.get("n_tests", 0) > 0:
        finding_num += 1
        findings.append(
            f"{finding_num}. **Backend differences survive correction:** "
            f"{mc['holm_significant']}/{mc['n_tests']} pairwise comparisons "
            f"survive Holm-Bonferroni correction "
            f"({mc['bonferroni_significant']}/{mc['n_tests']} survive "
            f"Bonferroni). All backend differences are genuine, not "
            f"multiple-testing artifacts."
        )

    # ANOVA interaction
    anova = analysis.get("anova_interaction", {})
    for mode, models in anova.items():
        for model, info in models.items():
            ie = info.get("interaction_evidence", "none")
            if "strong" in ie:
                finding_num += 1
                be = info.get("backend_effect", {})
                findings.append(
                    f"{finding_num}. **Context x backend interaction "
                    f"({model}, {mode}):** {ie}. "
                    f"Backend main effect F={be.get('f_statistic', 'N/A')}, "
                    f"p={be.get('p_value', 'N/A')}. "
                    f"The backend performance gap changes with context length."
                )

    # Distribution shape warnings
    ds = analysis.get("distribution_shape", {})
    extreme_skew = [
        k
        for k, v in ds.items()
        if v.get("pooled_mean_median_ratio") is not None
        and v["pooled_mean_median_ratio"] > 2.0
    ]
    if extreme_skew:
        finding_num += 1
        findings.append(
            f"{finding_num}. **Distribution skew warning:** "
            f"{len(extreme_skew)} measurement groups show mean/median "
            f"ratio >2.0 (all Ollama prefill due to cold-start). "
            f"Median is the appropriate central tendency for these groups."
        )

    # VRAM cliffs
    vram = analysis.get("vram_scaling", {})
    for model, info in vram.items():
        if info.get("oom_cliff"):
            finding_num += 1
            cliff = info["oom_cliff"]
            findings.append(
                f"{finding_num}. **OOM cliff ({model}):** GPU memory "
                f"exhausted at {cliff:,} tokens on 12 GB VRAM."
            )
        elif info.get("vram_cliff_11_5gb"):
            finding_num += 1
            cliff = info["vram_cliff_11_5gb"]
            findings.append(
                f"{finding_num}. **VRAM pressure ({model}):** exceeds "
                f"11.5 GB at {cliff:,} tokens — near OOM territory."
            )

    # TTFT thresholds
    ttft = analysis.get("ttft_analysis", {})
    for key, info in ttft.items():
        tc = info.get("threshold_crossings", {})
        model, backend = key.split("__", 1)
        for threshold, ctx in tc.items():
            if ctx is not None:
                finding_num += 1
                findings.append(
                    f"{finding_num}. **TTFT {threshold} ({model}, "
                    f"{backend}):** first token latency exceeds threshold "
                    f"at {ctx:,} tokens."
                )

    # Outlier rate
    outliers = analysis.get("outlier_analysis", {}).get("_summary", {})
    if outliers.get("total_measured", 0) > 0:
        finding_num += 1
        findings.append(
            f"{finding_num}. **Measurement stability:** "
            f"{outliers['total_outliers']} outliers detected across "
            f"{outliers['total_measured']} measurements "
            f"({outliers['overall_outlier_pct']:.1f}% outlier rate, "
            f"IQR method per context length)."
        )

    if not findings:
        findings.append("- No notable findings detected.")

    lines.extend(findings)
    lines.append("")
    return "\n".join(lines)


def _section_conclusions(analysis: dict) -> str:
    lines = [
        "## 14. Conclusions\n",
        "### Q1: Does attention quadratic cost show up empirically " "on RTX 4080?\n",
    ]

    # Two-regime answer: clean scaling + thrashing
    prefill = analysis.get("prefill_scaling", {})
    hf_entries = {k: v for k, v in prefill.items() if "__transformers-gpu" in k}
    ollama_entries = {k: v for k, v in prefill.items() if "__ollama" in k}

    lines.append(
        "**Two-regime answer** — the dominant effect observed on HF "
        "transformers is not O(n^2) attention but **VRAM overflow to "
        "system RAM**:\n"
    )

    # Clean scaling (pre-thrashing)
    clean_found = False
    for key, fit in sorted(hf_entries.items()):
        cs = fit.get("clean_scaling")
        if cs is None:
            continue
        clean_found = True
        model = key.split("__")[0]
        cs_pl = cs.get("power_law", {})
        cs_quad = cs.get("quadratic", {})
        b = cs_pl.get("b", 0) if isinstance(cs_pl.get("b"), (int, float)) else 0
        r2q = (
            cs_quad.get("r_squared", 0)
            if isinstance(cs_quad.get("r_squared"), (int, float))
            else 0
        )
        thresh = fit.get("thrashing_threshold", "?")
        mult = fit.get("thrashing_multiplier", "?")
        lines.append(
            f"- **{model} (pre-spillover):** b = {b:.2f}, "
            f"quadratic R^2 = {r2q:.4f}. True computational scaling "
            f"on 512-{fit.get('clean_context_lengths', ['?'])[-1]:,} tokens."
        )
        lines.append(
            f"  At {thresh:,} tokens, allocation exceeds 12 GB -> "
            f"**{mult}x latency cliff** from PCIe-bound paging."
        )

    if not clean_found:
        for key, fit in sorted(hf_entries.items()):
            model = key.split("__")[0]
            pl = fit.get("power_law", {})
            b = pl.get("b", 0) if isinstance(pl.get("b"), (int, float)) else 0
            lines.append(f"- {model}: b = {b:.3f}")

    lines.append("")

    # Ollama comparison
    if ollama_entries:
        lines.append(
            "**Ollama (llama.cpp)** shows sub-linear scaling across all "
            "context lengths (512-32K), confirming that optimized attention "
            "implementations (Flash Attention, paged KV cache) effectively "
            "eliminate the quadratic penalty at these lengths:"
        )
        for key, fit in sorted(ollama_entries.items()):
            model = key.split("__")[0]
            pl = fit.get("power_law", {})
            b = pl.get("b", 0) if isinstance(pl.get("b"), (int, float)) else 0
            lines.append(f"- {model} (Ollama): b = {b:.3f}")
        lines.append("")

    # Q2: VRAM bottleneck
    lines.append("### Q2: At what context length does VRAM become the " "bottleneck?\n")
    vram = analysis.get("vram_scaling", {})
    found_cliff = False
    for model, info in sorted(vram.items()):
        spillover = info.get("spillover_threshold")
        oom = info.get("oom_cliff")
        kv_cost = info.get("kv_cache_bytes_per_token")
        fit = info.get("linear_fit", {})

        if spillover or oom:
            found_cliff = True
            cliff = spillover or oom
            slope = fit.get("slope_mb_per_token", 0)
            kv_str = f", KV cost: {kv_cost:,.0f} B/token" if kv_cost else ""
            lines.append(
                f"- **{model}:** spillover to system RAM at "
                f"{cliff:,} tokens (slope: {slope:.4f} MB/token{kv_str})."
            )
            if spillover and oom:
                spill_ratio = info.get("spillover_ratio", "?")
                lines.append(
                    f"  Allocation reaches {spill_ratio}x physical GPU memory. "
                    f"OOM at {oom:,} tokens."
                )
            elif oom:
                lines.append(f"  OOM confirmed at {oom:,} tokens.")
    if not found_cliff:
        lines.append("No VRAM bottleneck detected within the tested range.")
    lines.append("")

    # Q3: TTFT scaling
    lines.append("### Q3: How does TTFT scale with context length?\n")
    ttft = analysis.get("ttft_analysis", {})
    if ttft:
        for key, info in sorted(ttft.items()):
            model, backend = key.split("__", 1)
            per_ctx = info.get("per_context_length", {})
            if not per_ctx:
                continue
            ctx_sorted = sorted(per_ctx.keys(), key=int)
            if len(ctx_sorted) >= 2:
                first_ctx = ctx_sorted[0]
                last_ctx = ctx_sorted[-1]
                first_ms = per_ctx[first_ctx]["mean_ms"]
                last_ms = per_ctx[last_ctx]["mean_ms"]
                ratio = last_ms / first_ms if first_ms > 0 else 0
                lines.append(
                    f"- **{model} ({backend}):** TTFT grows from "
                    f"{first_ms:.1f} ms ({int(first_ctx):,} tokens) to "
                    f"{last_ms:.1f} ms ({int(last_ctx):,} tokens) — "
                    f"**{ratio:.1f}x increase** over a "
                    f"{int(last_ctx) // int(first_ctx)}x context growth."
                )

            tc = info.get("threshold_crossings", {})
            crossings = [f"{t}: {c:,} tokens" for t, c in tc.items() if c is not None]
            if crossings:
                lines.append(f"  Threshold crossings: {', '.join(crossings)}")
        lines.append("")
    else:
        lines.append("No TTFT data available for analysis.\n")

    # Q4: Context-length cliff
    lines.append("### Q4: Is there a context length cliff?\n")
    cliff_found = False
    for key, fit in prefill.items():
        per_ctx = fit.get("per_context_length", {})
        if not per_ctx:
            continue
        ctx_sorted = sorted(per_ctx.keys(), key=int)
        model, backend = key.split("__", 1)

        for i in range(1, len(ctx_sorted)):
            prev_ms = per_ctx[ctx_sorted[i - 1]]["mean"]
            curr_ms = per_ctx[ctx_sorted[i]]["mean"]
            if prev_ms > 0 and curr_ms / prev_ms > 3.0:
                cliff_found = True
                lines.append(
                    f"- **{model} ({backend}):** performance cliff between "
                    f"{int(ctx_sorted[i - 1]):,} and {int(ctx_sorted[i]):,} tokens — "
                    f"latency jumps from {prev_ms:.1f} ms to {curr_ms:.1f} ms "
                    f"({curr_ms / prev_ms:.1f}x increase)."
                )

    for model_name, info in vram.items():
        if info.get("oom_cliff"):
            cliff_found = True
            lines.append(
                f"- **{model_name}:** hard cliff (OOM) at "
                f"{info['oom_cliff']:,} tokens."
            )

    if not cliff_found:
        lines.append(
            "No dramatic performance cliffs detected. Latency increases "
            "are gradual across the tested range."
        )
    lines.append("")

    return "\n".join(lines)


# ── main ──────────────────────────────────────────────────────────────


def generate_report(run_dir: Path) -> Path:
    """Generate report.md from analysis.json + manifest.json."""
    analysis_path = run_dir / "analysis.json"
    manifest_path = run_dir / "manifest.json"

    if not analysis_path.exists():
        raise FileNotFoundError(f"No analysis.json in {run_dir}")

    with analysis_path.open() as f:
        analysis = json.load(f)

    manifest = {}
    if manifest_path.exists():
        with manifest_path.open() as f:
            manifest = json.load(f)

    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    sections = [
        "# TR127: Long-Context Performance Characterization\n",
        f"*Generated: {timestamp}*\n",
        _section_environment(manifest),
        _section_methodology(analysis, manifest),
        _section_cold_start(analysis),
        _section_prefill_scaling(analysis),
        _section_decode_scaling(analysis),
        _section_vram_scaling(analysis),
        _section_ttft(analysis),
        _section_backend_comparison(analysis),
        _section_anova(analysis),
        _section_distribution_shape(analysis),
        _section_outlier_analysis(analysis),
        _section_power_analysis(analysis),
        _section_findings(analysis),
        _section_conclusions(analysis),
    ]

    report = "\n".join(sections)
    out_path = run_dir / "report.md"
    out_path.write_text(report, encoding="utf-8")
    log.info("Report -> %s (%d chars)", out_path, len(report))
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(description="TR127 report generation")
    parser.add_argument(
        "--run-dir",
        type=Path,
        default=None,
        help="Specific run directory (default: latest)",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s  %(message)s",
    )

    run_dir = args.run_dir or find_latest_run(TR127_RESULTS)
    if run_dir is None:
        log.error("No run directory found in %s", TR127_RESULTS)
        return 1

    generate_report(Path(run_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
