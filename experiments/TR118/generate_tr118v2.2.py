#!/usr/bin/env python3
"""
Generate TR118 v2.2 report by correcting v2.1 with verified audit data.
"""

from __future__ import annotations

import json
import math
import re
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _fmt_int(val: float | int) -> str:
    return f"{int(round(val)):,}"


def _fmt_float(val: float, digits: int = 2) -> str:
    return f"{val:.{digits}f}"


def _replace_section(text: str, start_heading: str, end_heading: str, new_section: str) -> str:
    start_idx = text.find(start_heading)
    if start_idx == -1:
        raise ValueError(f"Start heading not found: {start_heading}")
    if end_heading:
        end_idx = text.find(end_heading, start_idx + len(start_heading))
        if end_idx == -1:
            raise ValueError(f"End heading not found: {end_heading}")
        return text[:start_idx] + new_section + text[end_idx:]
    return text[:start_idx] + new_section


def _sanitize_ascii(text: str) -> str:
    replacements = {
        "×": "x",
        "–": "-",
        "—": "-",
        "−": "-",
        "’": "'",
        "“": '"',
        "”": '"',
        "…": "...",
        "≈": "~",
        "≤": "<=",
        "≥": ">=",
        "→": "->",
        "•": "-",
        "ƒ": "",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    return text.encode("ascii", "ignore").decode("ascii")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _throughput_mean(path: Path, backend: str) -> float:
    df = pd.read_csv(path)
    if "degraded_rate" in df.columns:
        df = df[df["degraded_rate"] < 1.0]
    agg = df.groupby("backend")["throughput_mean_tok_s"].mean()
    return float(agg[backend])


def _backend_success_table(raw_roots: list[Path]) -> dict[str, Any]:
    def is_degraded(row: dict[str, Any]) -> bool:
        if str(row.get("status", "ok")) != "ok":
            return True
        return int(row.get("degraded_count", 0) or 0) > 0

    stats: dict[str, dict[str, dict[str, int]]] = {}
    for root in raw_roots:
        for path in root.glob("bench_*_*.jsonl"):
            mode = "generate" if "generate" in path.name else "prefill"
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                backend = row.get("spec", {}).get("backend", "unknown")
                stats.setdefault(
                    backend,
                    {"prefill": {"total": 0, "degraded": 0}, "generate": {"total": 0, "degraded": 0}},
                )
                stats[backend][mode]["total"] += 1
                if is_degraded(row):
                    stats[backend][mode]["degraded"] += 1
    return stats


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    v21_path = repo_root / "PublishReady/reports/Technical_Report_118_v2.1.md"
    out_path = repo_root / "reports/generated/Technical_Report_118_v2.2.md"

    audit_dir = repo_root / "scripts/tr118/results/tr118v2_audit"
    run_counts = _load_json(audit_dir / "run_counts.json")
    tiny_check = _load_json(audit_dir / "tiny_model_check.json")
    trt_failures = _load_json(audit_dir / "trt_failures.json")
    amort = _load_json(audit_dir / "amortization_check.json")
    crossover = _load_json(audit_dir / "crossover_fit.json")

    text = _read_text(v21_path)

    # Header update
    header_anchor = "## Measurement Definitions"
    header_idx = text.find(header_anchor)
    if header_idx == -1:
        raise ValueError("Header anchor not found")

    total_runs = 0
    degraded_runs = 0
    for model in run_counts["models"].values():
        for summary in model["summaries"]:
            total_runs += int(summary["total_runs"])
            degraded_runs += int(summary["degraded_runs"])
    degraded_rate = degraded_runs / total_runs if total_runs else 0.0

    header = "\n".join(
        [
            "# Technical Report 118v2.2: Model Scale Comparative Analysis",
            "",
            "## ONNX Runtime + TensorRT Performance Across 1,210x Parameter Scaling",
            "",
            "**Project:** Banterhearts LLM Performance Research",
            f"**Date:** {date.today().isoformat()}",
            "**Author:** Research Team",
            "**Report Type:** Corrected Multi-Scale ONNX/TensorRT Analysis",
            f"**Test Duration:** {total_runs} total benchmark runs (360 prefill + 360 generate)",
            "**Related Work:** [TR118](Technical_Report_118.md) (Pipeline Validation), [TR117](Technical_Report_117.md) (Cross-Backend Baseline), [TR115_v2](Technical_Report_115_v2.md) (Runtime Analysis)",
            "",
            "**v2.2 Corrections from v2.1:**",
            "",
            "- Verified run counts and degradation rates from JSONL data (200/720 degraded, 27.8%)",
            "- Re-fit crossover power-law with 9 data points (5M, 25M, 50M, 75M, 100M, 45M validation)",
            "- Corrected tiny-gpt2 specs (vocab size 50,257; n_embd=2; perplexity interpretation)",
            "- Classified TensorRT failures as hard profile mismatches (no timeouts observed)",
            "- Fixed amortization math and token break-even calculation",
            "",
            "---",
            "",
            "## Abstract",
            "",
            "TR118v2.2 reports a corrected scaling study of ONNX Runtime and TensorRT across a 1,210x",
            "parameter span (0.103M to 124.4M). We benchmark six backends across six scenarios with",
            "five repetitions each (720 runs total) on an RTX 4080 Laptop system, measuring prefill",
            "and uncached generate latency/throughput, plus accuracy via WikiText-2 perplexity. A",
            "log-log power law fit over nine measured points places the ONNX CPU/PyTorch crossover at",
            "~76M parameters (95% CI 56M-120M). TensorRT INT8 speedup grows from 1.35x to 2.96x from",
            "tiny-gpt2 to GPT-2, while ONNX CPU inverts from 21.9x faster to 0.68x. All TensorRT",
            "generate runs fail with profile mismatch errors, so decode conclusions are deferred. We",
            "provide corrected artifact metadata, amortization math, and reproducibility guidance.",
            "",
            "---",
            "",
            header_anchor,
            "",
        ]
    )
    text = header + text[header_idx + len(header_anchor) + 1 :]

    # Executive Summary
    points = crossover["points"]
    fit = crossover["fit"]
    crossover_params = float(fit["crossover_params"])
    ci_low, ci_high = fit["crossover_ci_95"]

    tiny_ratio = points[0]["ratio"]
    gpt2_ratio = points[-1]["ratio"]

    tiny_prefill = repo_root / "scripts/tr118/results/tr118v2/20251213_135135_deep/tiny-gpt2/processed/latency_summary_prefill.csv"
    gpt2_prefill = repo_root / "scripts/tr118/results/tr118v2/20251213_135135_deep/gpt2/processed/latency_summary_prefill.csv"
    tiny_int8 = _throughput_mean(tiny_prefill, "tensorrt-int8")
    gpt2_int8 = _throughput_mean(gpt2_prefill, "tensorrt-int8")
    gpt2_base = _throughput_mean(gpt2_prefill, "transformers-gpu-compile")

    exec_summary = "\n".join(
        [
            "## Executive Summary",
            "",
            "This report provides a data-verified analysis of ONNX Runtime and TensorRT scaling across a",
            "1,210x parameter span (0.103M to 124.4M). The study includes 720 benchmark runs",
            "(360 prefill + 360 generate) across 6 backends, 6 scenarios, 2 models, 5 repetitions.",
            f"Overall degraded rate is {degraded_rate*100:.1f}% ({degraded_runs}/{total_runs}), driven by TensorRT",
            "profile mismatches in generate mode and FP16 batch prefill.",
            "",
            "### Key Findings (overall means across 6 scenarios)",
            "",
            "- Crossover: ONNX CPU advantage decays with scale and inverts between 50M and 75M params.",
            f"  A log-log power-law fit yields k={_fmt_float(fit['slope_k'], 3)} and a crossover at",
            f"  ~{_fmt_int(crossover_params/1e6)}M params (95% CI {_fmt_int(ci_low/1e6)}M-{_fmt_int(ci_high/1e6)}M).",
            f"- ONNX CPU vs PyTorch: {tiny_ratio:.2f}x faster at 0.103M, {gpt2_ratio:.2f}x at 124.4M.",
            f"- TensorRT scaling: INT8 improves from {tiny_int8/_throughput_mean(tiny_prefill, 'transformers-gpu-compile'):.2f}x",
            f"  (tiny-gpt2) to {gpt2_int8/gpt2_base:.2f}x (gpt2).",
            "- Generate mode: all TensorRT generate runs fail with hard profile mismatch errors",
            "  (set_input_shape_failed, cuMemcpyHtoDAsync invalid argument). No timeouts observed.",
            "- Perplexity: GPT-2 accuracy is preserved (<0.022% delta). Tiny-gpt2 perplexity",
            "  ~50,286 matches a near-uniform distribution over vocab size 50,257.",
            "",
            "---",
            "",
        ]
    )
    text = _replace_section(text, "## Executive Summary", "## Table of Contents", exec_summary)

    # Section 3.1
    tiny_vocab = int(tiny_check["vocab_size"])
    tiny_params = int(tiny_check["parameter_count"])
    tiny_ppl = float(tiny_check["perplexity_baseline"]["perplexity"])
    tiny_ratio_uniform = float(tiny_check["ratio_vs_uniform"])

    section_3_1 = "\n".join(
        [
            "### 3.1 Tiny-GPT2 (0.103M Parameters)",
            "",
            "**Model:** `models/tiny-gpt2` (local test fixture based on `sshleifer/tiny-gpt2`)",
            "",
            "**Architecture:**",
            "",
            "- **Layers:** 2",
            "- **Hidden size:** 2",
            "- **Attention heads:** 2",
            f"- **Vocabulary size:** {tiny_vocab} (standard GPT-2)",
            "- **Context length:** 1024",
            "",
            f"**Parameter Count:** {_fmt_int(tiny_params)} (0.103M)",
            "",
            "- Note: This model is untrained. Perplexity is near-uniform over the full vocab.",
            f"  Baseline perplexity {tiny_ppl:.3f} is {tiny_ratio_uniform:.6f}x the uniform value {tiny_vocab}.",
            "",
            "**Artifact Sizes:**",
            "",
            "- **PyTorch model:** 2.40 MB (`pytorch_model.bin`)",
            "- **ONNX export:** 0.86 MB (906,907 bytes)",
            "- **TRT FP32 engine:** 5.25 MB (163 layers, 5 profiles)",
            "- **TRT FP16 engine:** 2.17 MB (33 layers, 1 profile - reused from smoke test)",
            "- **TRT INT8 engine:** 3.62 MB (186 layers, 6 profiles)",
            "",
        ]
    )
    text = _replace_section(text, "### 3.1 Tiny-GPT2 (0.103M Parameters)", "### 3.2 GPT-2 (124.4M Parameters)", section_3_1)

    # Section 5: Crossover Phenomenon
    rows = []
    for point in points:
        params_m = point["parameter_count"] / 1e6
        rows.append(
            "| {model} | {params} | {onnx} | {pt} | {ratio} |".format(
                model=Path(point["model_ref"]).name if point["model_ref"] else "unknown",
                params=_fmt_float(params_m, 2),
                onnx=_fmt_int(point["onnx_cpu_tput"]),
                pt=_fmt_int(point["pytorch_tput"]),
                ratio=_fmt_float(point["ratio"], 2),
            )
        )
    crossover_section = "\n".join(
        [
            "## 5. The Crossover Phenomenon",
            "",
            "We measure ONNX Runtime CPU vs PyTorch (transformers-gpu-compile) using prefill",
            "overall mean throughput. The advantage decays with scale and crosses between 50M and 75M.",
            "",
            "| Model | Params (M) | ONNX CPU tok/s | PyTorch tok/s | Ratio |",
            "|-------|------------|---------------|---------------|-------|",
            *rows,
            "",
            "### Power-law Fit",
            "",
            "We fit a log-log power-law: log(A) = log(A0) + k * log(P), where A is the ONNX/PyTorch ratio.",
            f"- k = {_fmt_float(fit['slope_k'], 3)}",
            f"- A0 = {_fmt_float(math.exp(fit['intercept_logA0']), 1)}",
            f"- Crossover (A=1) at ~{_fmt_int(crossover_params/1e6)}M params",
            f"- 95% CI: {_fmt_int(ci_low/1e6)}M to {_fmt_int(ci_high/1e6)}M",
            "",
            "### Interpretation",
            "",
            "- ONNX CPU remains faster at 45M and 50M (ratios > 1).",
            "- At 75M, ONNX CPU is slower (ratio 0.72), and at 124M it is 0.68x.",
            "- The 100M point (0.86x) suggests variance; the aggregate fit still places the",
            "  crossover near ~76M with a wide CI.",
            "",
        ]
    )
    text = _replace_section(text, "## 5. The Crossover Phenomenon", "## 6. TensorRT Scaling Analysis", crossover_section)

    # Section 7: Generate Mode Degradation
    failure_counts = trt_failures["failures"]
    failure_rows = []
    for key, count in sorted(failure_counts.items()):
        backend, mode, ftype = key.split(":")
        failure_rows.append(f"| {backend} | {mode} | {ftype} | {count} |")
    section_7 = "\n".join(
        [
            "## 7. Generate Mode Degradation Analysis",
            "",
            "### 7.1 TensorRT Failure Classification",
            "",
            "Raw JSONL logs show hard failures (profile mismatch), not timeouts.",
            "All TensorRT generate runs are degraded across both models.",
            "",
            "| Backend | Mode | Failure Type | Count (both models) |",
            "|---------|------|--------------|---------------------|",
            *failure_rows,
            "",
            "**Observed errors:**",
            "",
            "- `set_input_shape_failed: input_ids: 4x19/4x27` (profile mismatch)",
            "- `LogicError: cuMemcpyHtoDAsync failed: invalid argument` (shape mismatch)",
            "",
            "### 7.2 Root Cause",
            "",
            "- Generate runs repeatedly call into engines with dynamic shapes.",
            "- Profile sets do not cover all generated shapes for these runs.",
            "- This is a hard failure in TensorRT shape handling, not a timeout.",
            "",
            "### 7.3 Implications",
            "",
            "- Prefill results are valid (all TRT backends succeed except FP16 batch edge cases).",
            "- Generate results for TRT are invalid until profiles match the decode shapes.",
            "- A KV-cache generate benchmark (use_cache=True) should be re-run with TRT-LLM or",
            "  engines built to cover decode shapes.",
            "",
            "---",
            "",
        ]
    )
    text = _replace_section(text, "## 7. Generate Mode Degradation Analysis", "## 8. Perplexity Validation", section_7)

    # Section 8.1
    section_8_1 = "\n".join(
        [
            "### 8.1 Tiny-GPT2 Perplexity",
            "",
            "**Dataset:** WikiText-2 test (72,531 tokens)",
            "",
            "| Backend | Perplexity | Pass | Note |",
            "|---------|-----------|------|------|",
            "| **transformers-gpu-compile** | 50,285.809 | OK | Baseline |",
            "| **onnxruntime-cpu** | 50,285.808 | OK | 0.000% delta |",
            "| **onnxruntime-gpu** | 50,285.808 | OK | 0.000% delta |",
            "| **tensorrt-fp32** | 50,285.808 | OK | 0.000% delta |",
            "| **tensorrt-int8** | 50,285.808 | OK | 0.000% delta |",
            "| **tensorrt-fp16** | NaN | FAIL | Degraded |",
            "",
            "**Interpretation:**",
            "",
            f"- Vocab size is {tiny_vocab}, not 256. Perplexity ~50,286 matches a near-uniform",
            "  distribution over the full GPT-2 vocab.",
            "- The model is untrained, so high perplexity is expected.",
            "- TensorRT FP16 fails due to profile mismatch in batch scenarios.",
            "",
        ]
    )
    text = _replace_section(text, "### 8.1 Tiny-GPT2 Perplexity", "### 8.2 GPT-2 Perplexity (Production Model)", section_8_1)

    # Section 9.2
    section_9_2 = "\n".join(
        [
            "### 9.2 Cost Analysis (GPT-2 Example)",
            "",
            f"**Baseline:** PyTorch GPU-compile, {_fmt_int(amort['baseline_throughput'])} tok/s",
            "",
            f"**TensorRT INT8:** {_fmt_int(amort['target_throughput'])} tok/s = {_fmt_float(amort['speedup_ratio'], 2)}x faster",
            "",
            "**Cost Reduction Calculation:**",
            "",
            "- Cost per token: 1 / throughput",
            f"- PyTorch: 1 / {_fmt_int(amort['baseline_throughput'])} = 0.000471 (relative)",
            f"- TRT INT8: 1 / {_fmt_int(amort['target_throughput'])} = 0.000159 (relative)",
            "- Reduction: 66% per token",
            "",
            "**Build Overhead:**",
            "",
            f"- One-time TRT INT8 build: {int(amort['build_time_s'])}s",
            f"- Time to recover: {_fmt_float(amort['time_to_recover_s'], 1)}s of inference",
            f"- Tokens to recover: {_fmt_int(amort['tokens_to_recover_baseline'])}",
            f"- Total tokens (build + recover): {_fmt_int(amort['total_tokens_baseline'])} (~0.77M)",
            "",
        ]
    )
    text = _replace_section(text, "### 9.2 Cost Analysis (GPT-2 Example)", "### 9.3 Recommended Stack", section_9_2)

    # Section 10.1 Key Findings
    section_10_1 = "\n".join(
        [
            "### 10.1 Key Findings",
            "",
            "**1. Crossover is Later Than Previously Reported**",
            "",
            "- ONNX CPU remains faster at 45M and 50M, but is slower at 75M and above.",
            f"- Power-law fit crossover: ~{_fmt_int(crossover_params/1e6)}M params",
            f"  (95% CI {_fmt_int(ci_low/1e6)}M-{_fmt_int(ci_high/1e6)}M).",
            "",
            "**2. TensorRT Scaling Improves With Model Size**",
            "",
            f"- Tiny-gpt2 INT8 vs PyTorch: {tiny_int8/_throughput_mean(tiny_prefill, 'transformers-gpu-compile'):.2f}x",
            f"- GPT-2 INT8 vs PyTorch: {gpt2_int8/gpt2_base:.2f}x",
            "",
            "**3. Generate Mode TRT Results Are Invalid**",
            "",
            "- All TensorRT generate runs fail with profile mismatch errors.",
            "- Prefill results remain valid; generate should be re-run with corrected profiles and KV cache.",
            "",
            "**4. Perplexity Preservation Holds**",
            "",
            "- GPT-2 deltas remain <0.022% for all successful backends.",
            "- Tiny-gpt2 perplexity matches uniform distribution over vocab size 50,257.",
            "",
        ]
    )
    text = _replace_section(text, "### 10.1 Key Findings", "### 10.2 Production Recommendations", section_10_1)

    # Section 10.3 Future Work
    section_10_3 = "\n".join(
        [
            "### 10.3 Future Work",
            "",
            "**TR119: Interpolation Study (Updated)**",
            "",
            "Focus on the crossover region with tighter spacing:",
            "",
            "- 40M, 50M, 60M, 70M, 80M, 90M params",
            "- Confirm crossover with repeated runs and variance bounds",
            "",
            "**TR120.B: KV-Cached Decode Study**",
            "TR120’s primary track is the compile-paradox investigation; KV-cached decode is tracked as TR120.B.",
            "",
            "- Re-benchmark generate with `use_cache=True` and TRT-LLM",
            "- Build TRT engines with profiles that cover decode shapes",
            "",
        ]
    )
    text = _replace_section(text, "### 10.3 Future Work", "## 11. Reproducibility", section_10_3)

    text = text.replace(
        "\n---\n\n## 10. Conclusions & Recommendations",
        "\n---\n\n## Discussion & Limitations\n\n"
        "The crossover behavior indicates CPU-optimized paths are viable only below ~50M parameters\n"
        "on this hardware, while GPU backends dominate beyond the transition band. TensorRT shows\n"
        "strong prefill scaling, but decode results are inconclusive because all TRT generate runs\n"
        "failed with profile mismatches. This limits any conclusions about end-to-end request cost\n"
        "without KV-cache support.\n\n"
        "Key limitations and threats to validity:\n\n"
        "- Single-machine study on an RTX 4080 Laptop GPU; datacenter GPUs and different CPUs may shift the crossover.\n"
        "- Generate benchmarks use `use_cache=False`, and TRT generate failures are pipeline artifacts.\n"
        "- Crossover fit combines two fully profiled models with additional CPU/PyTorch points from prior runs.\n"
        "- Batch sizes are limited to 1 and 4; larger batch regimes remain untested.\n\n"
        "---\n\n## 10. Conclusions & Recommendations",
    )

    # Section 13: Crossover Deep Dive
    section_13 = "\n".join(
        [
            "## 13. ONNX CPU Crossover Deep Dive",
            "",
            "This section re-fits the crossover curve using 9 measured points",
            "(0.103M, 5M, 11.18M, 25M, 45M, 50M, 75M, 100M, 124.4M).",
            "",
            "### 13.1 Fit Results",
            "",
            f"- k = {_fmt_float(fit['slope_k'], 3)}",
            f"- A0 = {_fmt_float(math.exp(fit['intercept_logA0']), 1)}",
            f"- Crossover: ~{_fmt_int(crossover_params/1e6)}M params",
            f"- 95% CI: {_fmt_int(ci_low/1e6)}M-{_fmt_int(ci_high/1e6)}M",
            "",
            "### 13.2 Empirical Transition",
            "",
            "- 45M: ONNX CPU 1.42x faster than PyTorch.",
            "- 50M: ONNX CPU 1.26x faster.",
            "- 75M: ONNX CPU 0.72x (slower).",
            "",
            "### 13.3 Recommendation",
            "",
            "- Treat 50M-75M as the transition band.",
            "- Use ONNX CPU below ~50M; prefer GPU paths at 75M+.",
            "",
        ]
    )
    text = _replace_section(text, "## 13. ONNX CPU Crossover Deep Dive", "## 14. TensorRT Architecture-Agnostic Optimization", section_13)

    # Section 15.3: Degradation stats
    stats = _backend_success_table(
        [
            repo_root / "scripts/tr118/results/tr118v2/20251213_135135_deep/tiny-gpt2/raw",
            repo_root / "scripts/tr118/results/tr118v2/20251213_135135_deep/gpt2/raw",
        ]
    )
    rows = []
    for backend in sorted(stats.keys()):
        pre = stats[backend]["prefill"]
        gen = stats[backend]["generate"]
        pre_ok = pre["total"] - pre["degraded"]
        gen_ok = gen["total"] - gen["degraded"]
        total = pre["total"] + gen["total"]
        total_ok = total - (pre["degraded"] + gen["degraded"])
        rows.append(
            "| {backend} | {pre_ok}/{pre_total} | {gen_ok}/{gen_total} | {total_ok}/{total} | {deg} |".format(
                backend=backend,
                pre_ok=pre_ok,
                pre_total=pre["total"],
                gen_ok=gen_ok,
                gen_total=gen["total"],
                total_ok=total_ok,
                total=total,
                deg=pre["degraded"] + gen["degraded"],
            )
        )

    section_15_3 = "\n".join(
        [
            "### 15.3 Degradation Rate Statistics",
            "",
            f"**Success Rate Analysis ({total_runs} total runs):**",
            "",
            "| Backend | Prefill Success | Generate Success | Overall Success | Degraded Count |",
            "|---------|----------------|------------------|-----------------|----------------|",
            *rows,
            "",
            "**Root Cause Analysis:**",
            "",
            "- TensorRT generate failures are profile mismatches (hard failures).",
            "- TensorRT FP16 also has 20 prefill failures in batch scenarios.",
            "- No timeouts were observed in the deep run JSONL logs.",
            "",
        ]
    )
    text = _replace_section(text, "### 15.3 Degradation Rate Statistics", "## 16. Conclusions & Final Recommendations", section_15_3)

    # Section 16: Conclusions & Final Recommendations
    section_16 = "\n".join(
        [
            "## 16. Conclusions & Final Recommendations",
            "",
            "### 16.1 Definitive Findings",
            "",
            "**1. Crossover Point is ~76M Params (CI 56M-120M)**",
            "",
            "- ONNX CPU stays faster through 50M, but is slower by 75M.",
            "- The 9-point fit places the crossover near 76M with wide CI.",
            "",
            "**2. TensorRT Scaling is Strong and Stable**",
            "",
            "- INT8 speedup increases from 1.35x (tiny) to 2.96x (gpt2).",
            "- FP16 remains a strong default for 10M-1B models.",
            "",
            "**3. TRT Generate Failures Are Profile Mismatches**",
            "",
            "- All generate failures are hard profile mismatch errors, not timeouts.",
            "- Prefill results remain valid; generate should be re-run with correct profiles/KV cache.",
            "",
            "### 16.2 Updated Decision Matrix",
            "",
            "| Model Size | Recommended Backend | Notes |",
            "|------------|---------------------|-------|",
            "| < 50M | ONNX CPU | Still faster than PyTorch on RTX 4080 system |",
            "| 50M-75M | Benchmark both | Transition band |",
            "| > 75M | TensorRT FP16/INT8 | GPU path preferred |",
            "",
            "### 16.3 Key Takeaways",
            "",
            "- CPU inference has a later crossover than initially predicted.",
            "- TensorRT delivers consistent gains when profiles match the workload.",
            "- Accuracy parity holds across successful backends.",
            "",
        ]
    )
    text = _replace_section(text, "## 16. Conclusions & Final Recommendations", "## 17. Reproducibility & Artifacts", section_16)

    # Addendum A update
    addendum = "\n".join(
        [
            "## Addendum A: Empirical Validation of Crossover (45M Model)",
            "",
            "The 45M validation run confirms ONNX CPU remains faster than PyTorch",
            "in the predicted transition region. The 45M point shows a 1.42x ONNX advantage,",
            "consistent with the updated crossover band between 50M and 75M.",
            "",
        ]
    )
    text = _replace_section(
        text,
        "## Addendum A: Empirical Validation of Crossover (45M Model)",
        "",
        addendum + "\n",
    )

    text = re.sub(
        r"- \*\*Generated:\*\* .*",
        f"- **Generated:** {date.today().isoformat()}",
        text,
    )
    text = text.replace(
        "**No degraded runs:** 100% success rate (180/180 runs)",
        "**Prefill degraded 10/180:** All degradations from TRT FP16 batch scenarios",
    )
    text = text.replace(
        "**All TensorRT backends degraded:** 90/90 runs hit 180s timeout",
        "**All TensorRT backends degraded:** 90/90 runs failed with profile mismatch errors (no timeouts)",
    )
    text = text.replace(
        '**Root cause:** Untrained model generates degenerate sequences ("stairs stairs stairs..."), TensorRT timeout due to profile mismatch (likely 1-profile FP16 engine reused)',
        "**Root cause:** Generate path hits profile mismatches; tiny FP16 engine has a single profile from the smoke run",
    )
    text = text.replace(
        "**No prefill degradations:** 170/180 runs successful (10 TRT FP16 batch degraded)",
        "**Prefill degraded 10/180:** All degradations from TRT FP16 batch scenarios",
    )
    text = text.replace(
        "1. **Artifact reuse:** FP16 engine was reused from smoke test\n"
        "2. **Profile mismatch:** Smoke test built only **1 optimization profile** (batch=1, max_seq=16)\n"
        "3. **Deep run requirements:** Needs **5 profiles** to cover batch=1-4, seq=8-128\n"
        "4. **Error observed:** `IExecutionContext::setInputShape: Static dimension mismatch`\n"
        "5. **Implication:** This is a **pipeline artifact issue**, NOT a TensorRT capability limitation",
        "1. **Profile mismatch:** Generate path submits shapes that violate TRT optimization profiles\n"
        "2. **Error observed:** `IExecutionContext::setInputShape: Static dimension mismatch`\n"
        "3. **Tiny-gpt2 FP16 engine:** Reused from smoke test (1 profile), explaining batch prefill failures\n"
        "4. **GPT-2 engines:** Built fresh with 5-6 profiles, yet generate still failed\n"
        "5. **Implication:** This is a **pipeline artifact issue**, NOT a TensorRT capability limitation",
    )
    text = text.replace("All degraded (100% timeout)", "All degraded (profile mismatch)")
    text = text.replace(
        "- Only two models tested: 0.103M and 124.4M params",
        "- Full multi-backend benchmarking covers two models (0.103M and 124.4M params)",
    )
    text = text.replace(
        "- Crossover point (~1M) is interpolated, not measured",
        "- Crossover fit uses additional CPU/PyTorch points from prior runs\n"
        "- Crossover point (~76M) is interpolated; transition band is 50M-75M",
    )
    text = text.replace(
        "**Note:** TensorRT FP16 batch scenarios degraded due to profile mismatch (only 1 profile in reused engine).",
        "**Note:** TensorRT FP16 batch scenarios degraded due to profile mismatch; see Section 7.",
    )
    text = text.replace(
        "- Generate benchmarks: 180-300s (180 runs, many timeouts for TRT)",
        "- Generate benchmarks: 180-300s (180 runs, many profile mismatch failures for TRT)",
    )
    text = text.replace(
        "- **TRT INT8 engine:** 3.62 MB (186 layers, 6 profiles)\n### 3.2 GPT-2 (124.4M Parameters)",
        "- **TRT INT8 engine:** 3.62 MB (186 layers, 6 profiles)\n\n### 3.2 GPT-2 (124.4M Parameters)",
    )
    text = text.replace(
        "TensorRT FP16 fails due to profile mismatch in batch scenarios.\n### 8.2 GPT-2 Perplexity (Production Model)",
        "TensorRT FP16 fails due to profile mismatch in batch scenarios.\n\n### 8.2 GPT-2 Perplexity (Production Model)",
    )
    text = text.replace(
        "- Total tokens (build + recover): 768,355 (~0.77M)\n### 9.3 Recommended Stack",
        "- Total tokens (build + recover): 768,355 (~0.77M)\n\n### 9.3 Recommended Stack",
    )
    text = text.replace(
        "- Tiny-gpt2 perplexity matches uniform distribution over vocab size 50,257.\n### 10.2 Production Recommendations",
        "- Tiny-gpt2 perplexity matches uniform distribution over vocab size 50,257.\n\n### 10.2 Production Recommendations",
    )
    text = text.replace(
        "## 16. Conclusions & Final Recommendations",
        "## 16. Synthesis & Decision Matrix\n\n"
        "This section is a quick-reference recap of validated findings. Conclusions are based on\n"
        "prefill performance; TensorRT generate remains invalid due to profile mismatches.",
    )
    text = text.replace("### 16.1 Definitive Findings", "### 16.1 Quick Reference Findings")
    text = text.replace("### 16.2 Updated Decision Matrix", "### 16.2 Decision Matrix (Prefill-Only)")
    text = _sanitize_ascii(text)
    _write_text(out_path, text)
    print(f"Wrote TR118 v2.2 report to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
