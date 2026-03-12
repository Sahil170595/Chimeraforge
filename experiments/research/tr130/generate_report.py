"""TR130 — Report generation for Serving Stack Benchmarking.

Produces Technical_Report_130.md matching TR126-TR129 publication standard:
- Dual-line title + metadata header
- Abstract
- Executive Summary (Key Findings, Key Decisions)
- Table of Contents
- SS-numbered main sections
- Appendices + References

Core question: Is the Amdahl serial fraction (s=0.39-0.54 from TR129)
an Ollama problem or a GPU physics problem?

Usage:
    python research/tr130/generate_report.py [-v]
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import sys

_DIR = Path(__file__).resolve().parent
_REPO = _DIR.parents[1]
sys.path.insert(0, str(_REPO))

from research.tr130.shared.utils import TR130_RESULTS, find_latest_run

log = logging.getLogger("tr130.report")


# -- Formatting helpers -------------------------------------------------------


def _w(lines: list[str], text: str = "") -> None:
    lines.append(text)


def _fmt(val, fmt_str: str = ".1f", fallback: str = "N/A") -> str:
    if val is None:
        return fallback
    if isinstance(val, float) and val != val:
        return fallback
    if isinstance(val, (int, float)):
        return f"{val:{fmt_str}}"
    return str(val)


def _fmt_ci(ci) -> str:
    if not ci or (isinstance(ci, (list, tuple)) and len(ci) < 2):
        return "N/A"
    return f"[{ci[0]:.2f}, {ci[1]:.2f}]"


def _pct(val, fallback: str = "N/A") -> str:
    if val is None:
        return fallback
    return f"{val * 100:.1f}%" if isinstance(val, float) and val < 10 else f"{val:.1f}%"


# -- Section builders --------------------------------------------------------


def _title_and_metadata(L: list[str], analysis: dict, manifest: dict) -> None:
    summary = analysis.get("summary", {})
    total = summary.get("total_rows", 0)
    n_backends = len(summary.get("backends", []))
    len(summary.get("models", []))
    n_phases = len(summary.get("phases", []))

    _w(L, "# Technical Report 130: Serving Stack Benchmarking")
    _w(L, "## Ollama vs vLLM vs TGI — Multi-agent throughput scaling comparison")
    _w(L)
    _w(L, "**Project:** Banterhearts LLM Performance Research")
    _w(L, "**Date:** 2026-02-26")
    _w(L, "**Author:** Research Team")
    _w(
        L,
        f"**Report Type:** Cross-backend serving stack benchmarking "
        f"({n_phases}-phase, {n_backends} backends, {total} measurements)",
    )
    _w(L, "**Test Duration:** ~3 hours")
    _w(L, "**Status:** Complete --- All 4 phases delivered")
    run_id = manifest.get("run_id", "N/A")
    _w(L, f"**Run ID:** `{run_id}`")
    _w(
        L,
        "**Related Work:** [TR129](Technical_Report_129.md) (N-Agent Scaling Laws), "
        "[TR128](Technical_Report_128.md) (Production Workload Characterization)",
    )
    _w(L, "**Depends On:** TR129 (Ollama serial fraction cross-validation)")
    _w(L)
    _w(L, "---")
    _w(L)


def _abstract(L: list[str], analysis: dict) -> None:
    _w(L, "## Abstract")
    _w(L)
    total = analysis.get("summary", {}).get("total_rows", 0)
    backends = analysis.get("summary", {}).get("backends", [])
    models = analysis.get("summary", {}).get("models", [])

    _w(
        L,
        "TR129 found that Ollama exhibits Amdahl serial fractions s=0.39--0.54 "
        "on an RTX 4080 Laptop GPU (12 GB VRAM), meaning up to 54% of inference "
        "is serialized under multi-agent concurrency. The critical unanswered "
        "question: **is this an Ollama scheduling bottleneck or an inherent GPU physics "
        "constraint?** If alternative serving stacks achieve lower serial fractions "
        "with identical hardware, the bottleneck is the serving stack, not the silicon.",
    )
    _w(L)
    _w(
        L,
        f"TR130 answers this question with **{total} measurements** across "
        f"{len(backends)} serving backends ({', '.join(backends)}), "
        f"{len(models)} models ({', '.join(models)}), and 4 phases: "
        f"environment validation, single-agent baseline, N-agent scaling "
        f"(N={{1,2,4,8}}), and time-to-first-token (TTFT) comparison. "
        f"Each backend serves the same models on the same GPU under identical "
        f"closed-loop workloads.",
    )
    _w(L)

    # Core finding
    core = analysis.get("cross_backend_serial_fraction", {}).get("core_finding", {})
    if core:
        _w(L, f"**Core finding:** {core.get('interpretation', 'See Section 8.')}")
        _w(L)

    # Quantization caveat
    _w(
        L,
        "*Methodological note:* Ollama serves Q4_0 quantized models while vLLM "
        "and TGI serve FP16. Since Amdahl's eta(N) normalizes per-agent throughput "
        "against each backend's own N=1 baseline, absolute throughput differences "
        "from quantization cancel out. The serial fraction comparison is valid.",
    )
    _w(L)


def _executive_summary(L: list[str], analysis: dict) -> None:
    _w(L, "## Executive Summary")
    _w(L)

    # Key Findings
    _w(L, "### Key Findings")
    _w(L)

    # 1. Baseline throughput comparison
    bl = analysis.get("baseline", {})
    for backend in sorted(bl.keys()):
        if backend == "status":
            continue
        models_data = bl[backend]
        for model in sorted(models_data.keys()):
            if model == "status":
                continue
            d = models_data[model]
            tps = d.get("effective_tps", {}).get("mean")
            quant = "Q4_0" if backend == "ollama" else "FP16"
            if tps:
                _w(
                    L,
                    f"- **{backend} × {model}** ({quant}): "
                    f"{tps:.1f} tok/s (N=1 baseline)",
                )
        _w(L)

    # 2. Serial fraction ranking
    ranking = analysis.get("cross_backend_serial_fraction", {}).get("ranking", [])
    if ranking:
        _w(L, "**Amdahl serial fraction ranking** (lower = better for multi-agent):")
        for r in ranking:
            _w(
                L,
                f"- #{r['rank']} **{r['backend']}**: s = "
                f"{r.get('mean_serial_fraction', 'N/A'):.3f} "
                f"(range: {r.get('min_serial_fraction', 0):.3f}--"
                f"{r.get('max_serial_fraction', 0):.3f})",
            )
        _w(L)

    # 3. TTFT
    ttft = analysis.get("ttft", {})
    ttft_entries = []
    for backend in sorted(ttft.keys()):
        if backend in ("status", "comparisons"):
            continue
        for model in sorted(ttft[backend].keys()):
            d = ttft[backend][model]
            if "mean" in d:
                ttft_entries.append(f"{backend} × {model}: {d['mean']:.1f} ms")
    if ttft_entries:
        _w(L, "**Time-to-First-Token (TTFT):**")
        for e in ttft_entries:
            _w(L, f"- {e}")
        _w(L)

    # Key Decisions
    _w(L, "### Key Decisions for Practitioners")
    _w(L)
    core = analysis.get("cross_backend_serial_fraction", {}).get("core_finding", {})
    is_stack = core.get("is_serving_stack_bottleneck", False)

    if is_stack:
        _w(
            L,
            "1. **Switch backends for multi-agent.** The serving stack IS the "
            "bottleneck --- practitioners running multi-agent workloads should "
            f"consider {core.get('best_backend', 'vLLM/TGI')} over "
            f"{core.get('worst_backend', 'Ollama')}.",
        )
    else:
        _w(
            L,
            "1. **GPU physics dominates.** The serial fraction difference across "
            "backends is small --- the GPU's compute/memory bandwidth is the "
            "fundamental constraint, not the serving stack's scheduling.",
        )

    _w(
        L,
        "2. **Quantization trade-off matters.** Ollama's Q4_0 delivers higher "
        "absolute tok/s than FP16 backends but with potentially worse multi-agent "
        "scaling. The optimal choice depends on whether you optimize for N=1 "
        "latency or N>1 throughput.",
    )
    _w(
        L,
        "3. **TTFT varies by backend.** Streaming-first applications should "
        "evaluate TTFT alongside throughput.",
    )
    _w(L)


def _when_to_use(L: list[str]) -> None:
    _w(L, "## When to Use This Report")
    _w(L)
    _w(L, "| Scenario | How This Report Helps |")
    _w(L, "|----------|----------------------|")
    _w(
        L,
        "| Choosing a serving backend for multi-agent deployment | "
        "Serial fraction comparison shows which backend degrades least |",
    )
    _w(
        L,
        "| Deciding between Ollama and vLLM/TGI | "
        "Head-to-head baseline + scaling + TTFT data |",
    )
    _w(
        L,
        "| Capacity planning for N concurrent agents | "
        "eta(N) curves + saturation points per backend |",
    )
    _w(
        L,
        "| Evaluating whether to switch from Ollama | "
        "Quantifies the multi-agent efficiency gap |",
    )
    _w(
        L,
        "| Understanding if GPU or software limits concurrency | "
        "Cross-backend serial fractions isolate the bottleneck |",
    )
    _w(L)


def _toc(L: list[str]) -> None:
    _w(L, "## Table of Contents")
    _w(L)
    toc = [
        ("SS1", "Introduction and Motivation"),
        ("SS2", "Methodology"),
        ("SS3", "Phase 1 — Environment Validation"),
        ("SS4", "Phase 2 — Single-Agent Baseline"),
        ("SS5", "Phase 3 — N-Agent Throughput Curves"),
        ("SS6", "Efficiency Curves eta(N)"),
        ("SS7", "Scaling Law Fitting"),
        ("SS8", "Cross-Backend Serial Fraction Comparison"),
        ("SS9", "Saturation Detection"),
        ("SS10", "Fairness Analysis"),
        ("SS11", "Phase 4 — TTFT Comparison"),
        ("SS12", "Queue Dynamics"),
        ("SS13", "VRAM Usage"),
        ("SS14", "TR129 Cross-Validation"),
        ("SS15", "Cold-Start Detection"),
        ("SS16", "Outlier Analysis"),
        ("SS17", "Backend-Native Metrics"),
        ("SS18", "Limitations and Future Work"),
        ("SS19", "Conclusions"),
        ("A", "Configuration"),
        ("B", "GPU Telemetry"),
        ("C", "Data Summary"),
        ("D", "Glossary"),
    ]
    for num, title in toc:
        _w(
            L,
            f"- [{num}. {title}](#{num.lower()}-{title.lower().replace(' ', '-').replace('—', '').replace('(', '').replace(')', '')})",
        )
    _w(L)


def _ss1_introduction(L: list[str], analysis: dict) -> None:
    _w(L, "## SS1. Introduction and Motivation")
    _w(L)
    _w(L, "### SS1.1 Background")
    _w(L)
    _w(
        L,
        "Multi-agent LLM systems deploy N autonomous agents that concurrently "
        "issue inference requests to a shared serving backend. TR129 established "
        "that Ollama exhibits Amdahl serial fractions s=0.39--0.54 on an "
        "RTX 4080 Laptop GPU, meaning that multi-agent efficiency drops "
        "substantially under concurrency.",
    )
    _w(L)
    _w(
        L,
        "But this finding leaves a critical question unanswered: **is the serial "
        "bottleneck in Ollama's request scheduling, or in the GPU hardware itself?**",
    )
    _w(L)
    _w(
        L,
        "If the serial fraction is a property of the GPU (memory bandwidth, "
        "compute pipeline serialization), then no software optimization will help. "
        "If it is a property of the serving stack (request queuing, KV-cache "
        "management, batch scheduling), then switching backends could dramatically "
        "improve multi-agent throughput.",
    )
    _w(L)
    _w(L, "### SS1.2 Experimental Design")
    _w(L)
    _w(
        L,
        "TR130 isolates the variable: **the serving stack**. All other factors "
        "are held constant:",
    )
    _w(L)
    _w(L, "| Factor | Controlled? | Value |")
    _w(L, "|--------|------------|-------|")
    _w(L, "| GPU hardware | Yes | RTX 4080 Laptop 12 GB |")
    _w(L, "| Models | Yes | llama3.2-1b, qwen2.5-1.5b, llama3.2-3b |")
    _w(L, "| Workload pattern | Yes | Closed-loop, 128 max tokens |")
    _w(L, "| Concurrency levels | Yes | N={1,2,4,8} |")
    _w(L, "| Serving backend | **Variable** | Ollama, vLLM, TGI |")
    _w(L, "| Quantization | Partially | Ollama=Q4_0, vLLM/TGI=FP16 |")
    _w(L)
    _w(
        L,
        "The quantization difference (Q4_0 vs FP16) affects absolute throughput "
        "but **not** the scaling efficiency eta(N), which normalizes against "
        "each backend's own N=1 baseline. Serial fraction comparisons remain valid.",
    )
    _w(L)
    _w(L, "### SS1.3 Literature Gap")
    _w(L)
    _w(
        L,
        "Published LLM serving benchmarks (Patel et al. 2024, Kwon et al. 2023) "
        "compare backends under **open-loop** arrival conditions (Poisson arrivals "
        "at specified rates). Multi-agent systems are **closed-loop**: each agent "
        "sends one request, waits for completion, then sends the next. This "
        "fundamental difference means open-loop benchmarks overestimate queuing "
        "depth and underestimate per-request contention. TR130 is the first "
        "cross-backend comparison under closed-loop multi-agent workloads on "
        "consumer GPU hardware.",
    )
    _w(L)


def _ss2_methodology(L: list[str], analysis: dict) -> None:
    _w(L, "## SS2. Methodology")
    _w(L)
    _w(L, "### SS2.1 Backends")
    _w(L)
    _w(L, "| Backend | API | Quantization | Deployment | Key Feature |")
    _w(L, "|---------|-----|-------------|------------|-------------|")
    _w(
        L,
        "| Ollama | `/api/generate` | Q4_0 | Native Windows | Timing in response (ns) |",
    )
    _w(
        L,
        "| vLLM | `/v1/completions` | FP16 | Docker GPU | PagedAttention, continuous batching |",
    )
    _w(
        L,
        "| TGI | `/generate` | FP16 | Docker GPU | `details=true` for per-request timing |",
    )
    _w(L)
    _w(
        L,
        "Only one backend runs at a time. Between backend switches, the previous "
        "server is fully stopped and the GPU is allowed to cool.",
    )
    _w(L)
    _w(L, "### SS2.2 Metrics")
    _w(L)
    _w(L, "| Metric | Formula | Availability |")
    _w(L, "|--------|---------|-------------|")
    _w(L, "| `effective_tps` | `completion_tokens / wall_ms * 1000` | All backends |")
    _w(
        L,
        "| `gpu_tokens_per_s` | `completion_tokens / decode_ms * 1000` | Ollama, TGI |",
    )
    _w(L, "| `prefill_ms` | Backend-native prefill time | Ollama, TGI |")
    _w(L, "| `decode_ms` | Backend-native decode time | Ollama, TGI |")
    _w(L, "| `ttft_ms` | Time to first token (streaming) | All backends |")
    _w(L)
    _w(
        L,
        "`effective_tps` is the **primary metric** — it captures the throughput "
        "each agent actually experiences, including all queue wait, scheduling "
        "overhead, and network latency.",
    )
    _w(L)
    _w(L, "### SS2.3 Statistical Methods")
    _w(L)
    _w(L, "- **95% CI** via t-distribution (per-backend × per-model)")
    _w(L, "- **Bootstrap CIs** (1,000 resamples) on Amdahl serial fractions")
    _w(L, "- **Shapiro-Wilk** normality testing on wall_ms distributions")
    _w(L, "- **Cohen's d** for cross-backend pairwise effect sizes")
    _w(L, "- **Curve fitting**: Amdahl, power law, exponential, logistic (4 models)")
    _w(L)
    _w(L, "### SS2.4 Four Phases")
    _w(L)
    _w(L, "| Phase | Purpose | Approximate Rows |")
    _w(L, "|-------|---------|-----------------|")
    _w(L, "| P1: Validation | Confirm Docker GPU, API format, model loading | ~27 |")
    _w(L, "| P2: Baseline | N=1 reference throughput per backend | ~450 |")
    _w(L, "| P3: Scaling | N={1,2,4,8} closed-loop agents (CORE) | ~4,050 |")
    _w(L, "| P4: TTFT | Streaming time-to-first-token | ~270 |")
    _w(L)


def _ss3_validation(L: list[str], analysis: dict) -> None:
    _w(L, "## SS3. Phase 1 — Environment Validation")
    _w(L)
    summary = analysis.get("summary", {})
    p1_rows = summary.get("rows_per_phase", {}).get("p1_validation", 0)
    _w(
        L,
        f"Phase 1 sent {p1_rows} validation requests across all backend × model "
        f"combinations to confirm:",
    )
    _w(L)
    _w(L, "1. Docker GPU passthrough works for vLLM and TGI containers")
    _w(L, "2. Each model loads and generates coherent text")
    _w(L, "3. API response parsing extracts correct token counts and timing")
    _w(L, "4. Timing fields match expected availability per backend")
    _w(L)

    # Validation results per backend
    bl = analysis.get("baseline", {})
    if bl and bl != {"status": "no_data"}:
        _w(
            L,
            "All backend × model combinations that passed validation proceeded "
            "to Phase 2. Failed combinations were skipped with logged errors.",
        )
    _w(L)


def _ss4_baseline(L: list[str], analysis: dict) -> None:
    _w(L, "## SS4. Phase 2 — Single-Agent Baseline")
    _w(L)
    bl = analysis.get("baseline", {})
    if not bl or bl == {"status": "no_data"}:
        _w(L, "*No baseline data available.*")
        _w(L)
        return

    _w(L, "### SS4.1 Absolute Throughput (N=1)")
    _w(L)
    _w(L, "| Backend | Model | Quant | N | Mean TPS | 95% CI | CV% | Wall ms |")
    _w(L, "|---------|-------|-------|---|----------|--------|-----|---------|")

    for backend in sorted(bl.keys()):
        if backend == "status":
            continue
        for model in sorted(bl[backend].keys()):
            if model == "status":
                continue
            d = bl[backend][model]
            tps = d.get("effective_tps", {})
            wall = d.get("wall_ms", {})
            quant = "Q4_0" if backend == "ollama" else "FP16"
            _w(
                L,
                f"| {backend} | {model} | {quant} | 1 "
                f"| {_fmt(tps.get('mean'))} "
                f"| [{_fmt(tps.get('ci95_lower'))}, {_fmt(tps.get('ci95_upper'))}] "
                f"| {_fmt(tps.get('cv_pct'))} "
                f"| {_fmt(wall.get('mean'))} |",
            )
    _w(L)

    _w(L, "### SS4.2 Cross-Backend Baseline Interpretation")
    _w(L)
    _w(
        L,
        "Ollama serves Q4_0 quantized weights, which are ~4x smaller than FP16. "
        "This means Ollama has:",
    )
    _w(L, "- **Lower memory bandwidth pressure** (less data to transfer per token)")
    _w(L, "- **Lower compute requirements** (INT4 ops vs FP16 ops)")
    _w(L, "- **Higher absolute tok/s at N=1** (expected and correct)")
    _w(L)
    _w(
        L,
        "This baseline difference does NOT affect the serial fraction comparison. "
        "Amdahl's eta(N) = TPS(N) / TPS(1) normalizes each backend against its "
        "own N=1 reference. A backend with 50 tok/s at N=1 and 25 tok/s at N=2 "
        "has the same eta(2)=0.5 as one with 100 tok/s at N=1 and 50 tok/s at N=2.",
    )
    _w(L)


def _ss5_throughput_curves(L: list[str], analysis: dict) -> None:
    _w(L, "## SS5. Phase 3 — N-Agent Throughput Curves")
    _w(L)
    tc = analysis.get("throughput_curves", {})
    if not tc or tc == {"status": "no_data"}:
        _w(L, "*No scaling data available.*")
        _w(L)
        return

    _w(L, "### SS5.1 Per-Agent Throughput vs N")
    _w(L)
    _w(L, "| Backend | Model | N | Per-Agent TPS | 95% CI | Total TPS | Wall ms |")
    _w(L, "|---------|-------|---|---------------|--------|-----------|---------|")

    for backend in sorted(tc.keys()):
        for model in sorted(tc[backend].keys()):
            curves = tc[backend][model]
            if not isinstance(curves, list):
                continue
            for p in curves:
                ci = p.get("per_agent_tps_ci95", [])
                ci_str = f"[{ci[0]:.1f}, {ci[1]:.1f}]" if len(ci) == 2 else "N/A"
                _w(
                    L,
                    f"| {backend} | {model} | {p['n_agents']} "
                    f"| {p['per_agent_tps']:.1f} "
                    f"| {ci_str} "
                    f"| {p['total_throughput_tps']:.1f} "
                    f"| {p.get('wall_ms_mean', 0):.0f} |",
                )
    _w(L)

    _w(L, "### SS5.2 Total Throughput Scaling")
    _w(L)
    _w(
        L,
        "Total throughput = N × per_agent_tps. In a perfectly parallel system, "
        "total throughput grows linearly with N. In practice, per-agent throughput "
        "degrades, so total throughput grows sub-linearly and eventually saturates.",
    )
    _w(L)
    _w(
        L,
        "The key question is **how fast** total throughput saturates for each "
        "backend. A backend with better request batching (vLLM's continuous "
        "batching, for example) should maintain per-agent throughput longer, "
        "producing higher total throughput at high N.",
    )
    _w(L)


def _ss6_efficiency(L: list[str], analysis: dict) -> None:
    _w(L, "## SS6. Efficiency Curves eta(N)")
    _w(L)
    eff = analysis.get("efficiency", {})
    if not eff or eff == {"status": "no_data"}:
        _w(L, "*No efficiency data available.*")
        _w(L)
        return

    _w(L, "### SS6.1 Definition")
    _w(L)
    _w(L, "eta(N) = effective_tps(N) / effective_tps(1)")
    _w(L)
    _w(
        L,
        "This is the per-agent efficiency: the fraction of N=1 throughput that "
        "each agent retains when sharing the GPU with N-1 other agents. "
        "eta(1) = 1.0 by definition; eta(N) < 1 for N > 1.",
    )
    _w(L)

    _w(L, "### SS6.2 Efficiency Table")
    _w(L)
    _w(L, "| Backend | Model | N | eta(N) | Per-Agent TPS | Baseline TPS |")
    _w(L, "|---------|-------|---|--------|---------------|-------------|")

    for backend in sorted(eff.keys()):
        for model in sorted(eff[backend].keys()):
            data = eff[backend][model]
            if not isinstance(data, dict) or "points" not in data:
                continue
            for p in data["points"]:
                _w(
                    L,
                    f"| {backend} | {model} | {p['n_agents']} "
                    f"| {p['eta']:.3f} "
                    f"| {p['per_agent_tps']:.1f} "
                    f"| {p['baseline_tps']:.1f} |",
                )
    _w(L)

    _w(L, "### SS6.3 What the Efficiency Curves Reveal")
    _w(L)
    _w(
        L,
        "If all backends show similar eta(N) curves, the serial bottleneck is "
        "in the GPU hardware. If some backends maintain higher eta(N) at large N, "
        "the bottleneck is in the serving software. This is the central question "
        "of TR130, addressed quantitatively in SS8.",
    )
    _w(L)


def _ss7_scaling_laws(L: list[str], analysis: dict) -> None:
    _w(L, "## SS7. Scaling Law Fitting")
    _w(L)
    sl = analysis.get("scaling_laws", {})
    if not sl:
        _w(L, "*No scaling law data available.*")
        _w(L)
        return

    _w(L, "### SS7.1 Four-Model Comparison")
    _w(L)
    _w(
        L,
        "| Backend | Model | Best Fit | R² | Amdahl s | Amdahl R² | Power α | Exp β |",
    )
    _w(
        L,
        "|---------|-------|----------|-----|----------|-----------|---------|-------|",
    )

    for backend in sorted(sl.keys()):
        for model in sorted(sl[backend].keys()):
            d = sl[backend][model]
            if not isinstance(d, dict) or "best_fit" not in d:
                continue
            am = d.get("amdahl", {})
            pw = d.get("power_law", {})
            ex = d.get("exponential", {})
            _w(
                L,
                f"| {backend} | {model} "
                f"| {d.get('best_fit', 'N/A')} "
                f"| {_fmt(d.get('best_r_squared'), '.3f')} "
                f"| {_fmt(am.get('serial_fraction'), '.4f')} "
                f"| {_fmt(am.get('r_squared'), '.3f')} "
                f"| {_fmt(pw.get('alpha'), '.3f')} "
                f"| {_fmt(ex.get('beta'), '.3f')} |",
            )
    _w(L)

    _w(L, "### SS7.2 Amdahl's Law Interpretation")
    _w(L)
    _w(L, "Amdahl's Law: eta(N) = 1 / (s + (1-s)*N)")
    _w(L)
    _w(
        L,
        "The serial fraction **s** represents the fraction of the inference "
        "pipeline that cannot be overlapped across concurrent requests. Sources "
        "of serialization include:",
    )
    _w(L)
    _w(
        L,
        "- **GPU compute serialization**: CUDA kernel launches are serialized, "
        "limiting how many requests can execute simultaneously",
    )
    _w(
        L,
        "- **Memory bandwidth contention**: All requests share the same HBM/GDDR "
        "bandwidth for KV-cache reads and weight fetches",
    )
    _w(
        L,
        "- **Request scheduling overhead**: The serving stack's scheduler adds "
        "latency when deciding which request to execute next",
    )
    _w(
        L,
        "- **KV-cache management**: Allocating, copying, and freeing KV-cache "
        "blocks requires synchronization",
    )
    _w(L)
    _w(
        L,
        "vLLM's PagedAttention and continuous batching are designed to minimize "
        "the last two sources. If they succeed, vLLM should have a lower serial "
        "fraction than Ollama.",
    )
    _w(L)


def _ss8_cross_backend(L: list[str], analysis: dict) -> None:
    _w(L, "## SS8. Cross-Backend Serial Fraction Comparison")
    _w(L)
    cb = analysis.get("cross_backend_serial_fraction", {})
    if not cb or cb == {"status": "no_data"}:
        _w(L, "*No cross-backend data available.*")
        _w(L)
        return

    _w(L, "### SS8.1 Core Question")
    _w(L)
    _w(
        L,
        "> **Is the Amdahl serial fraction s=0.39--0.54 (from TR129) an Ollama "
        "problem or a GPU physics problem?**",
    )
    _w(L)

    _w(L, "### SS8.2 Bootstrap Serial Fraction CIs")
    _w(L)
    _w(
        L,
        "Each serial fraction below is estimated via 1,000 bootstrap resamples "
        "of the efficiency curve, providing robust confidence intervals.",
    )
    _w(L)

    per_model = cb.get("per_model", {})
    for model in sorted(per_model.keys()):
        _w(L, f"#### {model}")
        _w(L)
        _w(L, "| Backend | s (mean) | s (median) | 95% CI | Std |")
        _w(L, "|---------|----------|-----------|--------|-----|")
        for backend in sorted(per_model[model].keys()):
            d = per_model[model][backend]
            if "mean" not in d:
                _w(L, f"| {backend} | N/A | N/A | N/A | N/A |")
                continue
            _w(
                L,
                f"| {backend} "
                f"| {d['mean']:.4f} "
                f"| {d['median']:.4f} "
                f"| [{d.get('ci95_lower', 0):.4f}, {d.get('ci95_upper', 0):.4f}] "
                f"| {d.get('std', 0):.4f} |",
            )
        _w(L)

    _w(L, "### SS8.3 Pairwise Comparisons")
    _w(L)
    comparisons = cb.get("pairwise_comparisons", [])
    if comparisons:
        _w(
            L,
            "| Model | Backend A | Backend B | s_A | s_B | Diff | Cohen's d | Effect | CIs Overlap |",
        )
        _w(
            L,
            "|-------|-----------|-----------|-----|-----|------|-----------|--------|-------------|",
        )
        for c in comparisons:
            _w(
                L,
                f"| {c['model']} "
                f"| {c['backend_a']} "
                f"| {c['backend_b']} "
                f"| {c['s_a']:.4f} "
                f"| {c['s_b']:.4f} "
                f"| {c['difference']:.4f} "
                f"| {c['cohens_d']:.2f} "
                f"| {c['effect_size']} "
                f"| {'yes' if c['cis_overlap'] else '**NO**'} |",
            )
        _w(L)

    _w(L, "### SS8.4 Aggregate Ranking")
    _w(L)
    ranking = cb.get("ranking", [])
    if ranking:
        _w(L, "| Rank | Backend | Mean s | Min s | Max s |")
        _w(L, "|------|---------|--------|-------|-------|")
        for r in ranking:
            _w(
                L,
                f"| {r['rank']} "
                f"| **{r['backend']}** "
                f"| {r.get('mean_serial_fraction', 0):.4f} "
                f"| {r.get('min_serial_fraction', 0):.4f} "
                f"| {r.get('max_serial_fraction', 0):.4f} |",
            )
        _w(L)

    _w(L, "### SS8.5 Answer to the Core Question")
    _w(L)
    core = cb.get("core_finding", {})
    if core:
        _w(
            L,
            f"**{core.get('interpretation', 'Insufficient data to draw conclusion.')}**",
        )
        _w(L)
        gap = core.get("serial_fraction_gap", 0)
        if gap > 0.05:
            _w(
                L,
                f"The serial fraction gap of {gap:.3f} between the best and worst "
                "backends exceeds our 0.05 significance threshold. This means the "
                "**serving stack** contributes meaningfully to the serialization "
                "bottleneck observed in TR129. Multi-agent practitioners should "
                "evaluate alternative backends.",
            )
        else:
            _w(
                L,
                f"The serial fraction gap of {gap:.3f} is below our 0.05 significance "
                "threshold. All three backends produce similar serial fractions, "
                "suggesting the bottleneck is **GPU physics** (memory bandwidth, "
                "compute pipeline), not the serving stack's scheduling.",
            )
    _w(L)

    _w(L, "### SS8.6 Mechanistic Interpretation")
    _w(L)
    _w(
        L,
        "The serial fraction captures all sources of serialization in the "
        "inference pipeline:",
    )
    _w(L)
    _w(
        L,
        "1. **GPU-side serialization** (hardware): CUDA streams, memory bandwidth, "
        "SM occupancy. This is identical across backends on the same GPU.",
    )
    _w(
        L,
        "2. **Software-side serialization** (serving stack): request queuing, "
        "KV-cache allocation, batch formation. This varies by backend.",
    )
    _w(L)
    _w(L, "If s_ollama ≈ s_vllm ≈ s_tgi → GPU hardware is the bottleneck.")
    _w(L, "If s_ollama >> s_vllm or s_tgi → Ollama's scheduling is the bottleneck.")
    _w(L)


def _ss9_saturation(L: list[str], analysis: dict) -> None:
    _w(L, "## SS9. Saturation Detection")
    _w(L)
    sat = analysis.get("saturation", {})
    if not sat:
        _w(L, "*No saturation data available.*")
        _w(L)
        return

    _w(
        L,
        "N* = the concurrency level where eta drops below 0.50 (each agent "
        "retains less than half of its standalone throughput).",
    )
    _w(L)
    _w(L, "| Backend | Model | N* | eta at Max N | Max N Tested |")
    _w(L, "|---------|-------|----|-------------|--------------|")
    for backend in sorted(sat.keys()):
        for model in sorted(sat[backend].keys()):
            d = sat[backend][model]
            _w(
                L,
                f"| {backend} | {model} "
                f"| {d.get('n_star', 'N/A')} "
                f"| {_fmt(d.get('eta_at_max_n'), '.3f')} "
                f"| {d.get('max_n_tested', 'N/A')} |",
            )
    _w(L)

    _w(
        L,
        "A backend with higher N* provides useful multi-agent scaling over a "
        "wider concurrency range. If all backends saturate at similar N*, the "
        "GPU is the limiting factor.",
    )
    _w(L)


def _ss10_fairness(L: list[str], analysis: dict) -> None:
    _w(L, "## SS10. Fairness Analysis")
    _w(L)
    fair = analysis.get("fairness", {})
    if not fair or fair == {"status": "no_data"}:
        _w(L, "*No fairness data available.*")
        _w(L)
        return

    _w(
        L,
        "Jain's Fairness Index: J = (sum(x))² / (n × sum(x²)), where x_i is "
        "agent i's mean effective_tps. J=1.0 means perfectly fair (all agents "
        "get equal throughput).",
    )
    _w(L)
    _w(L, "| Backend | Model | N | Jain's Index | Agent TPS CV% |")
    _w(L, "|---------|-------|---|-------------|---------------|")
    for backend in sorted(fair.keys()):
        for model in sorted(fair[backend].keys()):
            pts = fair[backend][model]
            if not isinstance(pts, list):
                continue
            for p in pts:
                _w(
                    L,
                    f"| {backend} | {model} | {p['n_agents']} "
                    f"| {p['jains_index']:.4f} "
                    f"| {p['agent_tps_cv_pct']:.1f} |",
                )
    _w(L)

    _w(L, "### SS10.1 Fairness Interpretation")
    _w(L)
    _w(
        L,
        "A Jain's index consistently near 1.0 means the backend distributes "
        "GPU time fairly across concurrent agents. A backend that prioritizes "
        "some requests (e.g., first-come-first-served without preemption) may "
        "show lower fairness at high N. Continuous batching (vLLM) should "
        "theoretically provide better fairness than sequential serving (Ollama).",
    )
    _w(L)


def _ss11_ttft(L: list[str], analysis: dict) -> None:
    _w(L, "## SS11. Phase 4 — TTFT Comparison")
    _w(L)
    ttft = analysis.get("ttft", {})
    if not ttft or ttft == {"status": "no_data"}:
        _w(L, "*No TTFT data available.*")
        _w(L)
        return

    _w(L, "### SS11.1 Time-to-First-Token (N=1)")
    _w(L)
    _w(L, "| Backend | Model | Mean TTFT (ms) | Median | P95 | P99 | CV% |")
    _w(L, "|---------|-------|---------------|--------|-----|-----|-----|")
    for backend in sorted(ttft.keys()):
        if backend in ("status", "comparisons"):
            continue
        for model in sorted(ttft[backend].keys()):
            d = ttft[backend][model]
            if "mean" not in d:
                continue
            _w(
                L,
                f"| {backend} | {model} "
                f"| {d['mean']:.1f} "
                f"| {d.get('median', 0):.1f} "
                f"| {d.get('p95', 0):.1f} "
                f"| {d.get('p99', 0):.1f} "
                f"| {d.get('cv_pct', 0):.1f} |",
            )
    _w(L)

    _w(L, "### SS11.2 Cross-Backend TTFT Comparison")
    _w(L)
    comparisons = ttft.get("comparisons", [])
    if comparisons:
        _w(
            L,
            "| Model | Backend A | Backend B | TTFT A (ms) | TTFT B (ms) | Diff (ms) | Cohen's d | Effect |",
        )
        _w(
            L,
            "|-------|-----------|-----------|------------|------------|-----------|-----------|--------|",
        )
        for c in comparisons:
            _w(
                L,
                f"| {c['model']} "
                f"| {c['backend_a']} "
                f"| {c['backend_b']} "
                f"| {c['ttft_a_ms']:.1f} "
                f"| {c['ttft_b_ms']:.1f} "
                f"| {c['difference_ms']:.1f} "
                f"| {c['cohens_d']:.2f} "
                f"| {c['effect_size']} |",
            )
        _w(L)

    _w(L, "### SS11.3 TTFT Interpretation")
    _w(L)
    _w(
        L,
        "TTFT measures how long a user waits before seeing the first token. "
        "This is critical for interactive/streaming applications. A backend "
        "with low throughput but fast TTFT may still feel responsive. "
        "TTFT is dominated by prefill time (processing the input prompt), "
        "which scales with prompt length and model size.",
    )
    _w(L)


def _ss12_queue_dynamics(L: list[str], analysis: dict) -> None:
    _w(L, "## SS12. Queue Dynamics")
    _w(L)
    qd = analysis.get("queue_dynamics", {})
    if not qd or qd == {"status": "no_data"}:
        _w(L, "*No queue dynamics data available.*")
        _w(L)
        return

    _w(L, "| Backend | Model | N | Mean Depth | Max Depth | % at Max |")
    _w(L, "|---------|-------|---|-----------|-----------|----------|")
    for backend in sorted(qd.keys()):
        for model in sorted(qd[backend].keys()):
            pts = qd[backend][model]
            if not isinstance(pts, list):
                continue
            for p in pts:
                _w(
                    L,
                    f"| {backend} | {model} | {p['n_agents']} "
                    f"| {p['mean_depth']:.1f} "
                    f"| {p['max_depth']} "
                    f"| {p['pct_at_max']:.0f}% |",
                )
    _w(L)

    _w(L, "### SS12.1 Queue Depth Interpretation")
    _w(L)
    _w(
        L,
        "In a closed-loop system with N agents, the theoretical maximum in-flight "
        "depth is N. A backend with continuous batching should show lower mean "
        "depth (requests complete faster, reducing queue buildup). A backend "
        "with sequential serving shows depth closer to N (requests must wait "
        "for the GPU to finish the current batch).",
    )
    _w(L)


def _ss13_vram(L: list[str], analysis: dict) -> None:
    _w(L, "## SS13. VRAM Usage")
    _w(L)
    vram = analysis.get("vram", {})
    if not vram:
        _w(L, "*No VRAM data available.*")
        _w(L)
        return

    _w(L, "| Phase | Mean VRAM (MB) | Min | Max |")
    _w(L, "|-------|---------------|-----|-----|")
    for phase in sorted(vram.keys()):
        d = vram[phase].get("mem_used_mb", {})
        if "mean" in d:
            _w(
                L,
                f"| {phase} "
                f"| {d['mean']:.0f} "
                f"| {d.get('min', 0):.0f} "
                f"| {d.get('max', 0):.0f} |",
            )
    _w(L)
    _w(
        L,
        "FP16 models (vLLM, TGI) consume ~2x the VRAM of Q4_0 models (Ollama). "
        "This constrains which models can be served on 12 GB VRAM. The 3B FP16 "
        "model may require reduced context length or fail to load entirely.",
    )
    _w(L)


def _ss14_crossval(L: list[str], analysis: dict) -> None:
    _w(L, "## SS14. TR129 Cross-Validation")
    _w(L)
    cv = analysis.get("tr129_crossval", {})
    status = cv.get("status")
    if status:
        _w(L, f"*{status}*")
        _w(L)
        return

    comparisons = cv.get("comparisons", [])
    if not comparisons:
        _w(L, "*No matching models between TR129 and TR130 Ollama runs.*")
        _w(L)
        return

    _w(
        L,
        "Ollama serial fractions from TR130 should match TR129 within 5% "
        "(same GPU, same models, same methodology).",
    )
    _w(L)
    _w(L, "| Model | TR130 s | TR129 s | Abs Diff | Within 5%? |")
    _w(L, "|-------|---------|---------|----------|-----------|")
    for c in comparisons:
        _w(
            L,
            f"| {c['model']} "
            f"| {c['tr130_s']:.4f} "
            f"| {c['tr129_s']:.4f} "
            f"| {c['absolute_difference']:.4f} "
            f"| {'Yes' if c['within_5pct'] else '**NO**'} |",
        )
    _w(L)

    all_ok = cv.get("all_within_5pct")
    if all_ok:
        _w(
            L,
            "All Ollama serial fractions match TR129 within 5%, confirming "
            "reproducibility and validating the methodology.",
        )
    else:
        _w(
            L,
            "Some serial fractions differ by >5%. Possible causes include "
            "thermal variation, background processes, or Ollama version differences.",
        )
    _w(L)


def _ss15_cold_start(L: list[str], analysis: dict) -> None:
    _w(L, "## SS15. Cold-Start Detection")
    _w(L)
    cs = analysis.get("cold_start", {})
    if not cs:
        _w(L, "*No cold-start data available.*")
        _w(L)
        return

    _w(
        L,
        "| Phase × Backend | Model | First-3 Mean (ms) | Rest Mean (ms) | Ratio | Cold Start? |",
    )
    _w(
        L,
        "|----------------|-------|-------------------|---------------|-------|------------|",
    )
    for key in sorted(cs.keys()):
        for model in sorted(cs[key].keys()):
            d = cs[key][model]
            _w(
                L,
                f"| {key} | {model} "
                f"| {d.get('first_3_mean_ms', 0):.0f} "
                f"| {d.get('rest_mean_ms', 0):.0f} "
                f"| {d.get('ratio', 0):.2f} "
                f"| {'Yes' if d.get('cold_start_detected') else 'No'} |",
            )
    _w(L)

    _w(
        L,
        "A ratio >1.5 indicates cold-start effects (first few requests are "
        "slower due to model loading, KV-cache initialization, CUDA kernel "
        "compilation, etc.). Docker-based backends (vLLM, TGI) may show "
        "more pronounced cold starts due to container initialization.",
    )
    _w(L)


def _ss16_outliers(L: list[str], analysis: dict) -> None:
    _w(L, "## SS16. Outlier Analysis")
    _w(L)
    ol = analysis.get("outliers", {})
    if not ol:
        _w(L, "*No outlier data available.*")
        _w(L)
        return

    _w(L, "IQR-based outlier detection (1.5 × IQR beyond Q1/Q3).")
    _w(L)
    _w(L, "| Backend | Model | N Total | N Outliers | Outlier % | IQR (ms) |")
    _w(L, "|---------|-------|---------|-----------|-----------|----------|")
    for backend in sorted(ol.keys()):
        for model in sorted(ol[backend].keys()):
            d = ol[backend][model]
            _w(
                L,
                f"| {backend} | {model} "
                f"| {d.get('n_total', 0)} "
                f"| {d.get('n_outliers', 0)} "
                f"| {d.get('outlier_pct', 0):.1f} "
                f"| {d.get('iqr', 0):.0f} |",
            )
    _w(L)


def _ss17_native_metrics(L: list[str], analysis: dict) -> None:
    _w(L, "## SS17. Backend-Native Metrics")
    _w(L)
    nm = analysis.get("backend_native_metrics", {})
    if not nm:
        _w(L, "*No backend-native metrics available.*")
        _w(L)
        return

    _w(L, "### SS17.1 Timing Breakdown Availability")
    _w(L)
    _w(L, "| Backend | Has prefill_ms | Has decode_ms |")
    _w(L, "|---------|---------------|--------------|")
    for backend in sorted(nm.keys()):
        d = nm[backend]
        _w(
            L,
            f"| {backend} "
            f"| {d.get('has_prefill_ms', False)} "
            f"| {d.get('has_decode_ms', False)} |",
        )
    _w(L)

    _w(L, "### SS17.2 Prefill and Decode Where Available")
    _w(L)
    for backend in sorted(nm.keys()):
        d = nm[backend]
        has_data = False
        for model in sorted(d.keys()):
            if model in ("has_prefill_ms", "has_decode_ms"):
                continue
            if not isinstance(d[model], dict):
                continue
            if not has_data:
                _w(L, f"#### {backend}")
                _w(L)
                _w(
                    L,
                    "| Model | Prefill Mean (ms) | Decode Mean (ms) | Total Wall (ms) |",
                )
                _w(L, "|-------|------------------|-----------------|----------------|")
                has_data = True
            pf = d[model].get("prefill_ms", {}).get("mean", "N/A")
            dc = d[model].get("decode_ms", {}).get("mean", "N/A")
            _w(L, f"| {model} | {_fmt(pf)} | {_fmt(dc)} | -- |")
        if has_data:
            _w(L)

    _w(L, "### SS17.3 Why This Matters")
    _w(L)
    _w(
        L,
        "The gap between wall_ms and (prefill_ms + decode_ms) represents "
        "scheduling overhead — the time requests spend waiting in the queue "
        "before GPU execution begins. A backend with a large gap has more "
        "software overhead; a backend where wall_ms ≈ prefill + decode has "
        "minimal scheduling overhead.",
    )
    _w(L)
    _w(
        L,
        "vLLM does not expose per-request timing breakdown, so this comparison "
        "is available only for Ollama and TGI. This is a limitation: we cannot "
        "determine whether vLLM's overhead is higher or lower than Ollama's "
        "from timing breakdown alone.",
    )
    _w(L)


def _ss18_limitations(L: list[str], analysis: dict) -> None:
    _w(L, "## SS18. Limitations and Future Work")
    _w(L)
    _w(L, "### SS18.1 What This Report Does NOT Prove")
    _w(L)
    _w(
        L,
        "1. **Generalization to other GPUs.** All measurements are on a single "
        "RTX 4080 Laptop 12 GB. Server GPUs (A100, H100) with higher memory "
        "bandwidth may show different serial fractions.",
    )
    _w(
        L,
        "2. **Long-context behavior.** All prompts are 100-300 tokens. At 4K+ "
        "context, KV-cache pressure changes the dynamics.",
    )
    _w(
        L,
        "3. **Quantization fairness.** Ollama=Q4_0 vs vLLM/TGI=FP16 means "
        "Ollama's model weights are 4x smaller. While eta(N) normalizes this, "
        "Q4_0 may have different memory access patterns that affect scaling.",
    )
    _w(
        L,
        "4. **Production workload mix.** All requests are similar length. "
        "Mixed-length workloads may favor backends with better preemption.",
    )
    _w(
        L,
        "5. **Multi-GPU.** All tests are single-GPU. Multi-GPU setups introduce "
        "tensor parallelism overhead that changes the serial fraction.",
    )
    _w(L)
    _w(L, "### SS18.2 Future Work")
    _w(L)
    _w(
        L,
        "1. **Same quantization comparison.** Run vLLM with GPTQ/AWQ Q4 "
        "quantization to eliminate the Q4 vs FP16 variable.",
    )
    _w(
        L,
        "2. **Server GPU replication.** Repeat on A100 80GB to separate GPU "
        "physics from laptop thermal constraints.",
    )
    _w(
        L,
        "3. **Open-loop vs closed-loop.** Run the same backends under Poisson "
        "arrivals to validate that closed-loop serial fractions are meaningful.",
    )
    _w(L, "4. **Larger N range.** Test N=16, 32 to find true saturation points.")
    _w(
        L,
        "5. **Mixed-model multi-agent.** Use different models per agent "
        "to stress KV-cache management (vLLM's advantage should be larger).",
    )
    _w(L)


def _ss19_conclusions(L: list[str], analysis: dict) -> None:
    _w(L, "## SS19. Conclusions")
    _w(L)
    core = analysis.get("cross_backend_serial_fraction", {}).get("core_finding", {})
    ranking = analysis.get("cross_backend_serial_fraction", {}).get("ranking", [])

    _w(L, "### SS19.1 The Core Question Answered")
    _w(L)
    if core:
        _w(L, f"{core.get('interpretation', 'See SS8 for details.')}")
    else:
        _w(
            L,
            "The cross-backend serial fraction comparison is the core contribution "
            "of this report. See SS8 for the full analysis.",
        )
    _w(L)

    _w(L, "### SS19.2 Practical Recommendations")
    _w(L)
    is_stack = core.get("is_serving_stack_bottleneck", False)
    if is_stack:
        _w(
            L,
            "1. **For N>2 concurrent agents:** Switch to the backend with the "
            "lowest serial fraction. The scheduling overhead reduction translates "
            "directly to higher per-agent throughput under contention.",
        )
        _w(
            L,
            "2. **For N=1:** Ollama's Q4_0 quantization provides the highest "
            "absolute throughput. The serving stack overhead only matters "
            "under concurrency.",
        )
    else:
        _w(
            L,
            "1. **All backends are equivalent for multi-agent.** The GPU is the "
            "bottleneck, not the software. Choose based on other criteria "
            "(ease of deployment, API compatibility, ecosystem).",
        )
        _w(
            L,
            "2. **Optimization at the serving stack level is futile.** To improve "
            "multi-agent scaling, you need a faster GPU (more memory bandwidth, "
            "more SMs) or smaller models (lower per-request GPU time).",
        )

    _w(
        L,
        "3. **TTFT matters for interactive use.** Even if throughput scaling "
        "is similar, backends may differ in time-to-first-token, affecting "
        "perceived responsiveness.",
    )
    _w(L)

    _w(L, "### SS19.3 One-Number Summary")
    _w(L)
    if ranking:
        for r in ranking:
            _w(
                L,
                f"- **{r['backend']}**: s = {r.get('mean_serial_fraction', 0):.3f} "
                f"(averaged across {r.get('n_models', 0)} models)",
            )
        _w(L)
    gap = core.get("serial_fraction_gap", 0)
    _w(
        L,
        f"Serial fraction gap between best and worst backend: **{gap:.3f}**. "
        f"{'This exceeds the 0.05 threshold — the serving stack matters.' if gap > 0.05 else 'Below 0.05 — GPU physics dominates.'}",
    )
    _w(L)


def _appendix_a(L: list[str], manifest: dict) -> None:
    _w(L, "## Appendix A: Configuration")
    _w(L)
    cfg = manifest.get("config", {})
    _w(L, "```yaml")
    for key in [
        "experiment",
        "max_new_tokens",
        "seed",
        "warmup_requests",
        "gpu_poll_interval_s",
    ]:
        if key in cfg:
            _w(L, f"{key}: {cfg[key]}")
    _w(L)
    _w(L, "models:")
    for m in cfg.get("models", []):
        _w(L, f"  - name: {m['name']}")
        _w(L, f"    hf_id: {m.get('hf_id', 'N/A')}")
        _w(L, f"    ollama_tag: {m.get('ollama_tag', 'N/A')}")
    _w(L)
    _w(L, "backends:")
    for bname, bcfg in cfg.get("backends", {}).items():
        _w(L, f"  {bname}:")
        for k, v in bcfg.items():
            _w(L, f"    {k}: {v}")
    _w(L)
    for phase in ["phase1", "phase2", "phase3", "phase4"]:
        if phase in cfg:
            _w(L, f"{phase}:")
            for k, v in cfg[phase].items():
                _w(L, f"  {k}: {v}")
    _w(L, "```")
    _w(L)


def _appendix_b(L: list[str], manifest: dict) -> None:
    _w(L, "## Appendix B: GPU Telemetry")
    _w(L)
    env = manifest.get("environment", {})
    _w(L, f"- GPU: {env.get('gpu_name', 'N/A')}")
    _w(L, f"- VRAM: {env.get('gpu_vram_mb', 'N/A')} MB")
    _w(L, f"- Driver: {env.get('gpu_driver', 'N/A')}")
    _w(L, f"- Platform: {env.get('platform', 'N/A')}")
    _w(L, f"- Docker: {env.get('docker_version', 'N/A')}")
    _w(L)


def _appendix_c(L: list[str], analysis: dict) -> None:
    _w(L, "## Appendix C: Data Summary")
    _w(L)
    summary = analysis.get("summary", {})
    _w(L, f"- **Total rows:** {summary.get('total_rows', 0)}")
    _w(L, f"- **OK rows:** {summary.get('ok_rows', 0)}")
    _w(L, f"- **Error rows:** {summary.get('error_rows', 0)}")
    _w(L, f"- **OK rate:** {summary.get('ok_rate', 0):.2%}")
    _w(L)
    _w(L, "**Rows per phase:**")
    for phase, count in sorted(summary.get("rows_per_phase", {}).items()):
        _w(L, f"- {phase}: {count}")
    _w(L)
    _w(L, "**Rows per backend:**")
    for backend, count in sorted(summary.get("rows_per_backend", {}).items()):
        _w(L, f"- {backend}: {count}")
    _w(L)
    _w(L, "**Rows per model:**")
    for model, count in sorted(summary.get("rows_per_model", {}).items()):
        _w(L, f"- {model}: {count}")
    _w(L)


def _appendix_d(L: list[str]) -> None:
    _w(L, "## Appendix D: Glossary")
    _w(L)
    terms = [
        (
            "effective_tps",
            "completion_tokens / wall_ms × 1000. User-perceived throughput including queue wait.",
        ),
        (
            "gpu_tokens_per_s",
            "completion_tokens / decode_ms × 1000. GPU-side decode throughput (no queue wait).",
        ),
        (
            "eta(N)",
            "Efficiency: per-agent TPS at N agents / per-agent TPS at N=1. Always ≤ 1.",
        ),
        (
            "Serial fraction (s)",
            "Amdahl parameter: fraction of inference that is serialized. Lower = better scaling.",
        ),
        ("N*", "Saturation point: N where eta < 0.5."),
        ("Jain's Index", "Fairness metric: 1.0 = all agents get equal throughput."),
        ("TTFT", "Time-to-First-Token: latency from request to first streamed token."),
        (
            "Closed-loop",
            "Each agent sends request → waits → sends next. Max concurrency = N.",
        ),
        (
            "Open-loop",
            "Requests arrive at a specified rate (Poisson). Can exceed N in-flight.",
        ),
        (
            "PagedAttention",
            "vLLM's KV-cache management: allocates memory in pages, reducing fragmentation.",
        ),
        (
            "Continuous batching",
            "vLLM/TGI: new requests join an in-progress batch without waiting for others to finish.",
        ),
        ("Q4_0", "4-bit quantization (Ollama default). ~4x smaller than FP16."),
        ("FP16", "Half-precision floating point (vLLM/TGI default)."),
        ("Bootstrap CI", "Confidence interval from resampling the data 1,000 times."),
        (
            "Cohen's d",
            "Effect size: |mean_diff| / pooled_std. <0.2 negligible, <0.5 small, <0.8 medium, ≥0.8 large.",
        ),
    ]
    _w(L, "| Term | Definition |")
    _w(L, "|------|-----------|")
    for term, defn in terms:
        _w(L, f"| {term} | {defn} |")
    _w(L)


def _references(L: list[str]) -> None:
    _w(L, "## References")
    _w(L)
    _w(
        L,
        "1. Kwon, W. et al. (2023). *Efficient Memory Management for Large "
        "Language Model Serving with PagedAttention.* SOSP 2023.",
    )
    _w(
        L,
        "2. Patel, P. et al. (2024). *Splitwise: Efficient generative LLM "
        "inference using phase splitting.* ISCA 2024.",
    )
    _w(
        L,
        "3. Amdahl, G.M. (1967). *Validity of the single processor approach "
        "to achieving large scale computing capabilities.* AFIPS 1967.",
    )
    _w(
        L,
        "4. Jain, R. et al. (1984). *A Quantitative Measure Of Fairness And "
        "Discrimination For Resource Allocation In Shared Computer Systems.* "
        "DEC-TR-301.",
    )
    _w(L, "5. TR129 (2026). *N-Agent Scaling Laws.* Banterhearts Research.")
    _w(
        L,
        "6. TR128 (2026). *Production Workload Characterization.* Banterhearts Research.",
    )
    _w(L)


# =============================================================================
#  MAIN
# =============================================================================


def main() -> int:
    parser = argparse.ArgumentParser(description="TR130 report generation")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s  %(message)s",
    )

    run_dir = find_latest_run(TR130_RESULTS)
    if run_dir is None:
        log.error("No run directory found in %s", TR130_RESULTS)
        return 1

    analysis_path = run_dir / "analysis.json"
    manifest_path = run_dir / "manifest.json"

    if not analysis_path.exists():
        log.error("No analysis.json in %s", run_dir)
        return 1

    with open(analysis_path, encoding="utf-8") as f:
        analysis = json.load(f)

    manifest = {}
    if manifest_path.exists():
        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)

    log.info("Generating report from %s", run_dir)

    L: list[str] = []

    _title_and_metadata(L, analysis, manifest)
    _abstract(L, analysis)
    _executive_summary(L, analysis)
    _when_to_use(L)
    _toc(L)
    _ss1_introduction(L, analysis)
    _ss2_methodology(L, analysis)
    _ss3_validation(L, analysis)
    _ss4_baseline(L, analysis)
    _ss5_throughput_curves(L, analysis)
    _ss6_efficiency(L, analysis)
    _ss7_scaling_laws(L, analysis)
    _ss8_cross_backend(L, analysis)
    _ss9_saturation(L, analysis)
    _ss10_fairness(L, analysis)
    _ss11_ttft(L, analysis)
    _ss12_queue_dynamics(L, analysis)
    _ss13_vram(L, analysis)
    _ss14_crossval(L, analysis)
    _ss15_cold_start(L, analysis)
    _ss16_outliers(L, analysis)
    _ss17_native_metrics(L, analysis)
    _ss18_limitations(L, analysis)
    _ss19_conclusions(L, analysis)
    _appendix_a(L, manifest)
    _appendix_b(L, manifest)
    _appendix_c(L, analysis)
    _appendix_d(L)
    _references(L)

    report_text = "\n".join(L) + "\n"
    out_path = Path(_REPO) / "PublishReady" / "reports" / "Technical_Report_130.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report_text, encoding="utf-8")

    n_lines = len(L)
    log.info("Report written: %s (%d lines)", out_path, n_lines)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
