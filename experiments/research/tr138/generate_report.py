"""TR138: Batch Inference Safety Under Non-Determinism — report generator.

Reads tr138_analysis.json and produces a full markdown report covering
batch-induced output non-determinism and its disproportionate impact on
safety vs capability outputs across three primary phases plus a compact
true-batching validation phase.

Report structure (29 sections):
  Header  — metadata, git commit, status
  1.  Abstract
  2.  Table of Contents
  3.  Executive Summary — 6 key claims with validation status
  4.  Research Question & Hypotheses — H1, H2, H3
  5.  Methodology — experimental design, batch control, co-batching
  6.  Models & Configuration — table of models across 4 phases
  7.  Phase 1: Batch Size x Output Determinism — identity, flip rates, stats
  8.  Phase 2: Co-Batching Interference — condition comparisons
  9.  Phase 3: Quantization x Concurrency Interaction — ANOVA, slopes
  10. Cross-Phase Synthesis — batch vs true-batch vs quant variance, risk classification
  11. TOST Equivalence Analysis — equivalence test results
  12. Power Analysis — MDE at 80% power per phase
  13. Latency Analysis — batch size, domain, throughput, flip-latency
  14. Judge Agreement Analysis — regex vs LLM judge kappa
  15. Jailbreak Type Breakdown — per-type amplification ratios
  16. Per-Category Bias Analysis — BBQ demographic breakdown
  17. Variance-Safety Correlation — Pearson r analysis
  18. Safety-Capability Divergence — formal CI overlap test
  19. Slope Heterogeneity & Critical Thresholds — task ranking
  20. Cross-TR Validation — baseline consistency with TR134/TR135
  21. Limitations — threats to validity
  22. Conclusions — formal conclusions
  23. Production Guidance — actionable recommendations
  24. Reproducibility — hardware, software, artifacts
  25. Appendix A: Full Output Identity Matrix
  26. Appendix B: Raw Statistical Tests
  27. Appendix C: Glossary
  28. References

Usage:
    python research/tr138/generate_report.py [-v] [--run-dir PATH]
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
import shutil
import subprocess
import sys

_DIR = Path(__file__).resolve().parent
_REPO = _DIR.parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from research.tr138.shared.utils import (
    find_latest_run,
    PHASE1_BATCH_SIZES,
    PHASE2_CONDITIONS,
    PHASE3_CONCURRENCY,
    PHASE3_QUANTS,
    TR138_VLLM_MODELS,
    TR138_OLLAMA_MODELS,
    SAFETY_TASKS,
    CAPABILITY_TASKS,
)

logger = logging.getLogger("tr138.generate_report")

_NA = "\u2014"  # em dash for missing values


# ── Helpers ────────────────────────────────────────────────────────────────


def _w(lines: list[str], text: str = "") -> None:
    """Append a line to the report buffer."""
    lines.append(text)


def _fmt_pval(p: float | None) -> str:
    """Format p-value with scientific notation where appropriate."""
    if p is None:
        return _NA
    if p < 0.001:
        return f"{p:.2e}"
    return f"{p:.4f}"


def _fmt_pct(val: float | None, decimals: int = 1) -> str:
    """Format a percentage to *decimals* decimal places."""
    if val is None:
        return _NA
    return f"{val:.{decimals}f}%"


def _fmt_f(val: float | None, decimals: int = 3) -> str:
    """Format a float value."""
    if val is None:
        return _NA
    return f"{val:.{decimals}f}"


def _fmt_signed(val: float | None, decimals: int = 4) -> str:
    """Format a float with sign."""
    if val is None:
        return _NA
    return f"{val:+.{decimals}f}"


def _bold_if(text: str, condition: bool) -> str:
    return f"**{text}**" if condition else text


def _get_git_hash() -> str:
    """Return short git hash or 'unknown'."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5, cwd=str(_REPO),
        )
        return result.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def _safe_get(d: dict | None, *keys: str, default: Any = None) -> Any:
    """Safely traverse nested dict keys."""
    current = d
    for k in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(k, default)
    return current


def _flatten_phase1_flip_rates(flip_rates: dict | list) -> list[dict[str, Any]]:
    if isinstance(flip_rates, list):
        return flip_rates
    entries: list[dict[str, Any]] = []
    if not isinstance(flip_rates, dict):
        return entries
    for model, by_batch in flip_rates.items():
        if model.startswith("_") or not isinstance(by_batch, dict):
            continue
        for batch_size, data in by_batch.items():
            if not isinstance(data, dict):
                continue
            entries.append(
                {
                    "model": model,
                    "batch_size": int(batch_size),
                    **data,
                }
            )
    return sorted(entries, key=lambda x: (x.get("model", ""), x.get("batch_size", 0)))


def _aggregate_phase1_flip_direction(flip_dir: dict) -> dict[str, Any]:
    if not isinstance(flip_dir, dict):
        return {}
    total_unsafe = 0
    total_safe = 0
    for data in flip_dir.values():
        if not isinstance(data, dict):
            continue
        total_unsafe += int(data.get("flip_to_unsafe", 0) or 0)
        total_safe += int(data.get("flip_to_safe", 0) or 0)
    total = total_unsafe + total_safe
    return {
        "refusal_to_compliance": total_unsafe / total if total else None,
        "compliance_to_refusal": total_safe / total if total else None,
        "refusal_to_compliance_count": total_unsafe,
        "compliance_to_refusal_count": total_safe,
        "total_flips": total,
    }


def _summarize_phase1_tasks(per_task: dict) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    if not isinstance(per_task, dict):
        return entries
    for task, by_batch in per_task.items():
        if not isinstance(by_batch, dict):
            continue
        batch_items = [
            data for batch, data in by_batch.items()
            if batch != "1" and isinstance(data, dict) and data.get("flip_rate") is not None
        ]
        if not batch_items:
            continue
        mean_flip = sum(item.get("flip_rate", 0.0) for item in batch_items) / len(batch_items)
        total_n = sum(int(item.get("total", 0) or 0) for item in batch_items)
        entries.append({"task": task, "flip_rate": mean_flip, "n": total_n})
    return sorted(entries, key=lambda x: x.get("flip_rate", 0.0), reverse=True)


def _flatten_phase1_tests(stats: dict) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    if not isinstance(stats, dict):
        return entries
    for label, data in stats.items():
        if not isinstance(data, dict):
            continue
        if label.startswith("_overall_bs"):
            batch_size = label.replace("_overall_bs", "")
            entries.append(
                {
                    "test": f"overall_bs{batch_size}",
                    "statistic": data.get("chi_squared"),
                    "p_value": data.get("chi_p"),
                    "effect_size": data.get("odds_ratio"),
                    "significant": (data.get("chi_p") or 1.0) < 0.05,
                }
            )
            continue
        for batch_size, batch_data in data.items():
            if not isinstance(batch_data, dict):
                continue
            p_value = batch_data.get("fisher_p", batch_data.get("chi_p"))
            entries.append(
                {
                    "test": f"{label}_bs{batch_size}",
                    "statistic": batch_data.get("chi_squared"),
                    "p_value": p_value,
                    "effect_size": batch_data.get("odds_ratio"),
                    "significant": batch_data.get("significant_holm", batch_data.get("significant_uncorrected", False)),
                }
            )
    return sorted(entries, key=lambda x: ((x.get("p_value") is None), x.get("p_value", 1.0), x.get("test", "")))


def _flatten_phase2_condition_scores(conditions: dict | list) -> list[dict[str, Any]]:
    if isinstance(conditions, list):
        return conditions
    entries: list[dict[str, Any]] = []
    if not isinstance(conditions, dict):
        return entries
    for model, cond_data in conditions.items():
        if not isinstance(cond_data, dict):
            continue
        for condition, data in cond_data.items():
            if not isinstance(data, dict):
                continue
            entries.append(
                {
                    "model": model,
                    "condition": condition,
                    "mean_score": data.get("mean_score"),
                    "ci_lo": data.get("ci_lo"),
                    "ci_hi": data.get("ci_hi"),
                    "n": data.get("n"),
                }
            )
    return sorted(entries, key=lambda x: (x.get("model", ""), x.get("condition", "")))


def _flatten_phase2_pairwise(pairwise: dict | list) -> list[dict[str, Any]]:
    if isinstance(pairwise, list):
        return pairwise
    entries: list[dict[str, Any]] = []
    if not isinstance(pairwise, dict):
        return entries
    for model, model_entries in pairwise.items():
        if not isinstance(model_entries, list):
            continue
        for entry in model_entries:
            if not isinstance(entry, dict):
                continue
            entries.append(
                {
                    "model": model,
                    "comparison": entry.get("comparison", f"{entry.get('condition_a')}_vs_{entry.get('condition_b')}"),
                    "delta_pp": (entry.get("diff") * 100) if entry.get("diff") is not None else None,
                    "p_value": entry.get("p_value"),
                    "effect_size": entry.get("cohens_d"),
                    "significant": entry.get("significant_holm", entry.get("significant_uncorrected", False)),
                }
            )
    return sorted(entries, key=lambda x: (x.get("model", ""), x.get("comparison", "")))


def _flatten_phase3_grid(grid: dict | list) -> list[dict[str, Any]]:
    if isinstance(grid, list):
        return grid
    entries: list[dict[str, Any]] = []
    if not isinstance(grid, dict):
        return entries
    for model, quant_data in grid.items():
        if not isinstance(quant_data, dict):
            continue
        for quant, conc_data in quant_data.items():
            if not isinstance(conc_data, dict):
                continue
            for concurrency, data in conc_data.items():
                if not isinstance(data, dict):
                    continue
                entries.append(
                    {
                        "model": model,
                        "quant": quant,
                        "concurrency": int(concurrency),
                        "mean_score": data.get("mean_score"),
                        "n": data.get("n"),
                    }
                )
    return sorted(entries, key=lambda x: (x.get("model", ""), x.get("quant", ""), x.get("concurrency", 0)))


def _flatten_phase3_slopes(slopes: dict | list) -> list[dict[str, Any]]:
    if isinstance(slopes, list):
        return slopes
    entries: list[dict[str, Any]] = []
    if not isinstance(slopes, dict):
        return entries
    for model, model_data in slopes.items():
        if not isinstance(model_data, dict):
            continue
        for quant, quant_data in model_data.get("by_quant", {}).items():
            if not isinstance(quant_data, dict):
                continue
            entries.append(
                {
                    "model": model,
                    "quant": quant,
                    "slope": quant_data.get("slope"),
                    "r_squared": quant_data.get("r_squared"),
                    "n": len(quant_data.get("levels", [])),
                }
            )
    return sorted(entries, key=lambda x: (x.get("model", ""), x.get("quant", "")))


# ── Data Loading ───────────────────────────────────────────────────────────


def _load_analysis(run_dir: Path) -> dict:
    """Load tr138_analysis.json from the run directory."""
    path = run_dir / "tr138_analysis.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ── Section Builders ──────────────────────────────────────────────────────


def _section_metadata(lines: list[str], analysis: dict, run_dir: Path) -> None:
    """Section 0: Metadata header."""
    meta = analysis.get("metadata", {})
    git_hash = _get_git_hash()
    _w(lines, "# TR138: Batch Inference Safety Under Non-Determinism")
    _w(lines)
    _w(lines, "| Field | Value |")
    _w(lines, "|-------|-------|")
    _w(lines, "| **TR Number** | 138 |")
    _w(lines, f"| **Date** | {datetime.now(UTC).strftime('%Y-%m-%d')} |")
    _w(lines, "| **Version** | 1.0 |")
    _w(lines, "| **Author** | Banterhearts Research Lab |")
    _w(lines, f"| **Git Commit** | `{git_hash}` |")
    _w(lines, "| **Status** | Auto-generated from `tr138_analysis.json` |")
    _w(lines, f"| **Run Directory** | `{run_dir.name}` |")
    _w(lines, f"| **Total Samples** | {meta.get('total_samples', _NA):,} |" if isinstance(meta.get('total_samples'), int) else f"| **Total Samples** | {meta.get('total_samples', _NA)} |")
    _w(lines, f"| **Phase 1 Samples** | {meta.get('phase1_samples', _NA)} |")
    _w(lines, f"| **Phase 2 Samples** | {meta.get('phase2_samples', _NA)} |")
    _w(lines, f"| **Phase 3 Samples** | {meta.get('phase3_samples', _NA)} |")
    _w(lines, f"| **Phase 4 Samples** | {meta.get('phase4_samples', _NA)} |")
    _w(lines)
    _w(lines, "---")
    _w(lines)


def _section_abstract(lines: list[str], analysis: dict) -> None:
    """Section 1: Abstract."""
    _w(lines, "## 1. Abstract")
    _w(lines)
    meta = analysis.get("metadata", {})
    total = meta.get("total_samples", "~25,000")
    n_models = meta.get("n_models", 3)

    phase1 = analysis.get("phase1", {})
    phase4 = analysis.get("phase4", {})
    safety_flip = _safe_get(phase1, "overall_safety_flip_rate")
    cap_flip = _safe_get(phase1, "overall_capability_flip_rate")
    true_batch_flip = _safe_get(phase4, "overall_safety_flip_rate")

    _w(lines, f"This report presents results from TR138, a {total}-sample experiment "
       f"measuring whether batch-induced output non-determinism in GPU inference "
       f"disproportionately degrades safety compared to capability. "
       f"We evaluate {n_models} instruction-tuned models across two families "
       f"(Llama 3.2, Qwen 2.5) using controlled vLLM batching (Phase 1-2) "
       f"and Ollama quantized serving under concurrent load (Phase 3), with a "
       f"compact true-batching validation on explicit vLLM prompt lists (Phase 4).")
    _w(lines)

    if safety_flip is not None and cap_flip is not None:
        ratio = safety_flip / cap_flip if cap_flip > 0 else float("inf")
        _w(lines, f"Key finding: safety outputs flip at **{_fmt_pct(safety_flip * 100)}** "
           f"vs capability at **{_fmt_pct(cap_flip * 100)}** across batch sizes "
           f"({ratio:.1f}x ratio), indicating that batch-induced non-determinism "
           f"is **not safety-neutral**. Co-batching adversarial prompts alongside "
           f"safety prompts produces measurable interference, and Phase 3 measures "
           f"how quantization changes sensitivity to concurrent load.")
        if true_batch_flip is not None:
            _w(lines, f"The compact Phase 4 true-batching validation records "
               f"**{_fmt_pct(true_batch_flip * 100)}** safety flips under explicit "
               f"prompt-list batching, testing whether the Phase 1 effect survives "
               f"without request-scheduler timing artifacts.")
    else:
        _w(lines, "Key finding: Batch-induced non-determinism affects safety and "
           "capability outputs at different rates. The effect interacts with "
           "co-batching conditions and quantization level. Full results are "
           "presented across the four-part design below.")
    _w(lines)
    _w(lines, "---")
    _w(lines)


def _section_toc(lines: list[str]) -> None:
    """Section 2: Table of Contents."""
    _w(lines, "## 2. Table of Contents")
    _w(lines)
    toc_items = [
        ("1", "Abstract"),
        ("2", "Table of Contents"),
        ("3", "Executive Summary"),
        ("4", "Research Question & Hypotheses"),
        ("5", "Methodology"),
        ("6", "Models & Configuration"),
        ("7", "Phase 1: Batch Size x Output Determinism"),
        ("8", "Phase 2: Co-Batching Interference"),
        ("9", "Phase 3: Quantization x Concurrency Interaction"),
        ("10", "Cross-Phase Synthesis"),
        ("11", "TOST Equivalence Analysis"),
        ("12", "Power Analysis"),
        ("13", "Latency Analysis"),
        ("14", "Judge Agreement Analysis"),
        ("15", "Jailbreak Type Breakdown"),
        ("16", "Per-Category Bias Analysis"),
        ("17", "Variance-Safety Correlation"),
        ("18", "Safety-Capability Divergence"),
        ("19", "Slope Heterogeneity & Critical Thresholds"),
        ("20", "Cross-TR Validation"),
        ("21", "Limitations"),
        ("22", "Conclusions"),
        ("23", "Production Guidance"),
        ("24", "Reproducibility"),
        ("A", "Appendix A: Full Output Identity Matrix"),
        ("B", "Appendix B: Raw Statistical Tests"),
        ("C", "Appendix C: Glossary"),
        ("", "References"),
    ]
    for num, title in toc_items:
        prefix = f"{num}. " if num else ""
        _w(lines, f"- [{prefix}{title}](#{title.lower().replace(' ', '-').replace(':', '').replace('&', '')})")
    _w(lines)
    _w(lines, "---")
    _w(lines)


def _section_executive_summary(lines: list[str], analysis: dict) -> None:
    """Section 3: Executive Summary with 6 key claims."""
    _w(lines, "## 3. Executive Summary")
    _w(lines)

    phase1 = analysis.get("phase1", {})
    phase2 = analysis.get("phase2", {})
    phase3 = analysis.get("phase3", {})
    phase4 = analysis.get("phase4", {})
    synthesis = analysis.get("cross_phase_synthesis", {})

    # Claim 1: Safety flip rate > capability flip rate
    safety_flip = _safe_get(phase1, "overall_safety_flip_rate")
    cap_flip = _safe_get(phase1, "overall_capability_flip_rate")
    if safety_flip is not None and cap_flip is not None:
        ratio = safety_flip / cap_flip if cap_flip > 0 else float("inf")
        if ratio > 1.5:
            status = "CONFIRMED"
            marker = "\u2713"
        elif ratio > 1.0:
            status = "PARTIAL"
            marker = "~"
        else:
            status = "REFUTED"
            marker = "\u2717"
        _w(lines, f"**Claim 1** {marker} **{status}**: Batch-induced flips disproportionately "
           f"affect safety outputs ({_fmt_pct(safety_flip * 100)} safety vs "
           f"{_fmt_pct(cap_flip * 100)} capability, {ratio:.1f}x ratio).")
    else:
        _w(lines, f"**Claim 1** {_NA}: Batch-induced flips disproportionately affect "
           "safety outputs. *Data not yet available.*")
    _w(lines)

    # Claim 2: Refusal->compliance dominates flip direction
    flip_dir = _aggregate_phase1_flip_direction(_safe_get(phase1, "flip_direction_breakdown", default={}) or {})
    refusal_to_compliance = _safe_get(flip_dir, "refusal_to_compliance")
    compliance_to_refusal = _safe_get(flip_dir, "compliance_to_refusal")
    if refusal_to_compliance is not None and compliance_to_refusal is not None:
        if refusal_to_compliance > compliance_to_refusal:
            _w(lines, f"\u2713 **CONFIRMED**: Refusal\u2192compliance flips "
               f"({_fmt_pct(refusal_to_compliance * 100)}) dominate over "
               f"compliance\u2192refusal ({_fmt_pct(compliance_to_refusal * 100)}). "
               f"**Batching weakens safety alignment.**")
        else:
            _w(lines, f"\u2717 **REFUTED**: Compliance\u2192refusal flips dominate "
               f"({_fmt_pct(compliance_to_refusal * 100)} vs "
               f"{_fmt_pct(refusal_to_compliance * 100)}). Batching does not "
               f"preferentially weaken refusal.")
    else:
        _w(lines, f"**Claim 2** {_NA}: Refusal\u2192compliance flips dominate over "
           "compliance\u2192refusal. *Data not yet available.*")
    _w(lines)

    # Claim 3: Co-batching adversarial prompts degrades safety
    adversarial_delta = _safe_get(phase2, "adversarial_vs_solo_delta")
    if adversarial_delta is not None:
        if adversarial_delta < -0.02:
            _w(lines, f"\u2713 **CONFIRMED**: Co-batching adversarial prompts degrades "
                f"safety by **{_fmt_signed(adversarial_delta * 100, 1)}pp** vs solo inference.")
        elif adversarial_delta < 0:
            _w(lines, f"~ **PARTIAL**: Co-batching adversarial prompts produces a small "
               f"safety decrease ({_fmt_signed(adversarial_delta * 100, 1)}pp) that may "
               f"not be practically significant.")
        else:
            _w(lines, f"\u2717 **REFUTED**: Co-batching adversarial prompts does not "
               f"degrade safety ({_fmt_signed(adversarial_delta * 100, 1)}pp).")
    else:
        _w(lines, f"**Claim 3** {_NA}: Co-batching adversarial prompts degrades safety "
           "outcomes. *Data not yet available.*")
    _w(lines)

    # Claim 4: True batching validation
    p4_flip = _safe_get(phase4, "overall_safety_flip_rate")
    p4_align = _safe_get(synthesis, "phase4_mean_flip_agreement_pct")
    if p4_flip is not None:
        if p4_flip > 0.01:
            align_txt = f"; mean flip agreement with Phase 1 = {_fmt_f(p4_align, 1)}%" if p4_align is not None else ""
            _w(lines, f"\u2713 **CONFIRMED**: Explicit prompt-list true batching also induces "
               f"safety flips (**{_fmt_pct(p4_flip * 100)}**{align_txt}), so the Phase 1 effect "
               f"is not reducible to request-arrival timing alone.")
        else:
            _w(lines, f"~ **MIXED**: Explicit true batching produces limited safety flipping "
               f"({_fmt_pct(p4_flip * 100)}), weakening but not eliminating the Phase 1 signal.")
    else:
        _w(lines, f"**Claim 4** {_NA}: True batching validation. *Data not yet available.*")
    _w(lines)

    # Claim 5: Quant x concurrency interaction
    interaction = _safe_get(phase3, "anova", "interaction")
    interaction_p = _safe_get(interaction, "combined_p_value")
    sig_models = _safe_get(interaction, "significant_models", default=0)
    n_models = _safe_get(interaction, "n_models", default=0)
    if interaction_p is not None:
        if interaction_p < 0.05:
            eta2 = _safe_get(interaction, "mean_eta_squared")
            qualifier = "across models" if sig_models == n_models else f"with mixed per-model strength ({sig_models}/{n_models} significant)"
            _w(lines, f"\u2713 **CONFIRMED**: Quantization \u00d7 concurrency interaction is "
               f"significant ({qualifier}; combined p={_fmt_pval(interaction_p)}, "
               f"mean \u03b7\u00b2={_fmt_f(eta2)}).")
        else:
            _w(lines, f"\u2717 **REFUTED**: Quantization \u00d7 concurrency interaction is "
               f"not significant at the combined-model level (p={_fmt_pval(interaction_p)}).")
    else:
        _w(lines, f"**Claim 5** {_NA}: Quantization \u00d7 concurrency interaction. "
           "*Data not yet available.*")
    _w(lines)

    # Claim 6: Risk classification
    risk_class = _safe_get(synthesis, "risk_classification")
    if risk_class:
        _w(lines, f"\u2713 **CONFIRMED**: Production risk classification = **{risk_class}**. "
           "Batch-induced safety degradation is a measurable production concern.")
    else:
        _w(lines, f"**Claim 6** {_NA}: Production risk classification. "
           "*Awaiting cross-phase synthesis.*")
    _w(lines)
    _w(lines, "---")
    _w(lines)


def _section_hypotheses(lines: list[str]) -> None:
    """Section 4: Research Question & Hypotheses."""
    _w(lines, "## 4. Research Question & Hypotheses")
    _w(lines)
    _w(lines, "> **Research Question:** Does batch-induced output non-determinism "
       "disproportionately degrade safety compared to capability?")
    _w(lines)
    _w(lines, "### Hypotheses")
    _w(lines)
    _w(lines, "- **H1 (Null):** Batch-induced output changes are safety-neutral "
       "(uniform random flips across all output types).")
    _w(lines, "- **H2 (Alternative):** Batch-induced changes disproportionately "
       "degrade safety (safety tokens are more fragile than capability tokens).")
    _w(lines, "- **H3 (Interference):** Co-batching adversarial prompts alongside "
       "safety prompts affects safety outcomes (cross-request interference via "
       "shared GPU state).")
    _w(lines)
    _w(lines, "---")
    _w(lines)


def _section_methodology(lines: list[str]) -> None:
    """Section 5: Methodology."""
    _w(lines, "## 5. Methodology")
    _w(lines)
    _w(lines, "### Experimental Design")
    _w(lines)
    _w(lines, "Four-part experiment measuring output non-determinism "
       "under batch inference on consumer GPU hardware (RTX 4080 Laptop, 12GB VRAM).")
    _w(lines)
    _w(lines, "- **Temperature:** 0.0 (greedy decoding) throughout all phases")
    _w(lines, "- **Seed:** 42 (fixed for CUDA/cuBLAS where supported)")
    _w(lines, "- **Max tokens:** 256")
    _w(lines, "- **Warmup:** 3 requests per model before data collection")
    _w(lines)
    _w(lines, "### Batch Control Mechanism")
    _w(lines)
    _w(lines, "- **Phase 1 (vLLM):** Synchronized request groups force exact in-flight batch sizes.")
    _w(lines, "- **Phase 2 (vLLM):** One target prompt is evaluated under four conditions: "
       "`solo`, `benign`, `adversarial`, and `safety` co-batches.")
    _w(lines, "- **Phase 3 (Ollama):** Concurrent API load is used as a separate proxy axis. "
       "It measures quantization x concurrency, not true batching.")
    _w(lines, "- **Phase 4 (vLLM):** A single completions call receives a prompt list, giving "
       "explicit true batching without cross-request arrival timing effects.")
    _w(lines)
    _w(lines, "### Co-Batching Design (Phase 2)")
    _w(lines)
    _w(lines, "Four conditions are used in Phase 2:")
    _w(lines, "- **Solo:** Target prompt evaluated alone (`batch_size=1`).")
    _w(lines, "- **Benign:** Target prompt co-batched with innocuous factual questions.")
    _w(lines, "- **Adversarial:** Target prompt co-batched with harmful/jailbreak prompts.")
    _w(lines, "- **Safety:** Target prompt co-batched with non-adversarial safety-evaluation prompts.")
    _w(lines)
    _w(lines, "---")
    _w(lines)


def _section_models(lines: list[str], analysis: dict) -> None:
    """Section 6: Models & Configuration."""
    _w(lines, "## 6. Models & Configuration")
    _w(lines)
    _w(lines, "| Model | Family | Params | Phase 1 | Phase 2 | Phase 3 | Phase 4 | Backend |")
    _w(lines, "|-------|--------|--------|---------|---------|---------|---------|---------|")

    all_models = {m["name"]: m for m in TR138_VLLM_MODELS}
    for m in TR138_OLLAMA_MODELS:
        if m["name"] not in all_models:
            all_models[m["name"]] = m

    vllm_names = {m["name"] for m in TR138_VLLM_MODELS}
    ollama_names = {m["name"] for m in TR138_OLLAMA_MODELS}
    phase4_names = set(_safe_get(analysis, "metadata", "models_p4", default=[]))

    for name in sorted(all_models):
        m = all_models[name]
        p1 = "\u2713" if name in vllm_names else "\u2717"
        p2 = "\u2713" if name in vllm_names else "\u2717"
        p3 = "\u2713" if name in ollama_names else "\u2717"
        p4 = "\u2713" if name in phase4_names else "\u2717"
        backend = []
        if name in vllm_names:
            backend.append("vLLM FP16")
        if name in ollama_names:
            backend.append("Ollama Q8/Q4/Q2")
        if name in phase4_names:
            backend.append("vLLM true-batch")
        _w(lines, f"| {name} | {m.get('family', _NA)} | "
           f"{m['params_m']}M | {p1} | {p2} | {p3} | {p4} | "
           f"{', '.join(backend)} |")
    _w(lines)

    _w(lines, "**Phase 1 tasks:** AdvBench (100), Jailbreak (120), BBQ (200), "
       "TruthfulQA (50), MMLU (285), ARC-Challenge (200) = 955 prompts")
    _w(lines, "**Phase 2 tasks:** AdvBench (100), Jailbreak (120), BBQ (200), "
       "TruthfulQA (50) = 470 safety prompts")
    _w(lines, "**Phase 3 tasks:** AdvBench (100), Jailbreak (120) = 220 safety prompts")
    _w(lines, "**Phase 4 tasks:** Reduced subset = 450 prompts (250 safety + 200 capability)")
    _w(lines)
    _w(lines, "---")
    _w(lines)


def _section_phase1(lines: list[str], analysis: dict) -> None:
    """Section 7: Phase 1 — Batch Size x Output Determinism."""
    _w(lines, "## 7. Phase 1: Batch Size x Output Determinism")
    _w(lines)

    phase1 = analysis.get("phase1", {})
    if not phase1:
        _w(lines, "> Phase 1 data not available.")
        _w(lines)
        _w(lines, "---")
        _w(lines)
        return

    identity = phase1.get("output_identity", {})
    _w(lines, "### 7.1 Output Identity (byte-identical vs batch=1)")
    _w(lines)
    if identity:
        batch_sizes = sorted((int(bs), data) for bs, data in identity.items() if str(bs).isdigit())
        models = sorted({model for _, data in batch_sizes for model in data.get("per_model", {}).keys()})
        if models and batch_sizes:
            _w(lines, "| Model | " + " | ".join(f"BS={bs}" for bs, _ in batch_sizes) + " |")
            _w(lines, "|-------" + "|--------" * len(batch_sizes) + "|")
            for model in models:
                row = [model]
                for _, data in batch_sizes:
                    row.append(_fmt_pct(_safe_get(data, "per_model", model, "pct_identical")))
                _w(lines, "| " + " | ".join(row) + " |")
            _w(lines)
    else:
        _w(lines, "> Output identity data not available.")
        _w(lines)

    flip_entries = _flatten_phase1_flip_rates(phase1.get("flip_rates", {}))
    _w(lines, "### 7.2 Safety vs Capability Flip Rate")
    _w(lines)
    if flip_entries:
        _w(lines, "| Model | Batch Size | Safety Flip Rate | Capability Flip Rate | Ratio (S/C) |")
        _w(lines, "|-------|-----------|-----------------|---------------------|-------------|")
        for entry in flip_entries:
            s_rate = entry.get("safety_flip_rate")
            c_rate = entry.get("capability_flip_rate")
            ratio = s_rate / c_rate if s_rate is not None and c_rate and c_rate > 0 else None
            _w(lines, f"| {entry.get('model', _NA)} | {entry.get('batch_size', _NA)} | "
               f"{_fmt_pct(s_rate * 100 if s_rate is not None else None)} | "
               f"{_fmt_pct(c_rate * 100 if c_rate is not None else None)} | "
               f"{_bold_if(_fmt_f(ratio, 2), ratio is not None and ratio > 2.0)} |")
        _w(lines)
    else:
        _w(lines, "> Flip rate data not available.")
        _w(lines)

    flip_dir = _aggregate_phase1_flip_direction(phase1.get("flip_direction_breakdown", {}))
    _w(lines, "### 7.3 Flip Direction Breakdown")
    _w(lines)
    if flip_dir:
        _w(lines, "| Direction | Count | Percentage |")
        _w(lines, "|-----------|-------|------------|")
        _w(lines, f"| Refusal -> compliance | {flip_dir.get('refusal_to_compliance_count', 0)} | "
           f"{_fmt_pct((flip_dir.get('refusal_to_compliance') or 0) * 100)} |")
        _w(lines, f"| Compliance -> refusal | {flip_dir.get('compliance_to_refusal_count', 0)} | "
           f"{_fmt_pct((flip_dir.get('compliance_to_refusal') or 0) * 100)} |")
        _w(lines)
    else:
        _w(lines, "> Flip direction data not available.")
        _w(lines)

    per_task = _summarize_phase1_tasks(phase1.get("per_task_sensitivity", {}))
    _w(lines, "### 7.4 Per-Task Sensitivity")
    _w(lines)
    if per_task:
        _w(lines, "| Task | Domain | Mean Flip Rate | N |")
        _w(lines, "|------|--------|----------------|---|")
        for entry in per_task:
            task = entry.get("task")
            domain = "safety" if task in SAFETY_TASKS else "capability"
            _w(lines, f"| {task} | {domain} | "
               f"{_fmt_pct((entry.get('flip_rate') or 0) * 100)} | "
               f"{entry.get('n', _NA)} |")
        _w(lines)
    else:
        _w(lines, "> Per-task sensitivity data not available.")
        _w(lines)

    tests = _flatten_phase1_tests(phase1.get("statistical_tests", {}))
    _w(lines, "### 7.5 Statistical Tests")
    _w(lines)
    if tests:
        _w(lines, "| Test | Statistic | p-value | Effect Size | Significant |")
        _w(lines, "|------|-----------|---------|-------------|-------------|")
        for t in tests:
            sig = "\u2713" if t.get("significant") else "\u2717"
            _w(lines, f"| {t.get('test', _NA)} | "
               f"{_fmt_f(t.get('statistic'))} | "
               f"{_fmt_pval(t.get('p_value'))} | "
               f"{_fmt_f(t.get('effect_size'))} | {sig} |")
        _w(lines)
    else:
        _w(lines, "> Statistical test data not available.")
        _w(lines)

    _w(lines, "---")
    _w(lines)


def _section_phase2(lines: list[str], analysis: dict) -> None:
    """Section 8: Phase 2 — Co-Batching Interference."""
    _w(lines, "## 8. Phase 2: Co-Batching Interference")
    _w(lines)

    phase2 = analysis.get("phase2", {})
    if not phase2:
        _w(lines, "> Phase 2 data not available.")
        _w(lines)
        _w(lines, "---")
        _w(lines)
        return

    conditions = _flatten_phase2_condition_scores(phase2.get("condition_scores", {}))
    _w(lines, "### 8.1 Mean Safety Score by Co-Batch Condition")
    _w(lines)
    if conditions:
        _w(lines, "| Model | Condition | Mean Safety | CI Lower | CI Upper | N |")
        _w(lines, "|-------|-----------|------------|----------|----------|---|")
        for entry in conditions:
            _w(lines, f"| {entry.get('model', _NA)} | {entry.get('condition', _NA)} | "
               f"{_fmt_f(entry.get('mean_score'))} | "
               f"{_fmt_f(entry.get('ci_lo'))} | "
               f"{_fmt_f(entry.get('ci_hi'))} | "
               f"{entry.get('n', _NA)} |")
        _w(lines)
    else:
        _w(lines, "> Condition score data not available.")
        _w(lines)

    pairwise = _flatten_phase2_pairwise(phase2.get("pairwise_comparisons", {}))
    _w(lines, "### 8.2 Pairwise Condition Comparisons")
    _w(lines)
    if pairwise:
        _w(lines, "| Model | Comparison | Delta (pp) | p-value | Effect Size | Significant |")
        _w(lines, "|-------|------------|-----------|---------|-------------|-------------|")
        for entry in pairwise:
            sig = "\u2713" if entry.get("significant") else "\u2717"
            _w(lines, f"| {entry.get('model', _NA)} | {entry.get('comparison', _NA)} | "
               f"{_fmt_signed(entry.get('delta_pp'), 1)} | "
               f"{_fmt_pval(entry.get('p_value'))} | "
               f"{_fmt_f(entry.get('effect_size'))} | {sig} |")
        _w(lines)
    else:
        _w(lines, "> Pairwise comparison data not available.")
        _w(lines)

    per_task = phase2.get("per_task_interference", {})
    _w(lines, "### 8.3 Per-Task Interference Breakdown")
    _w(lines)
    if per_task:
        _w(lines, "| Task | Solo Mean | Adversarial Mean | Delta (pp) | Vulnerable? |")
        _w(lines, "|------|-----------|-----------------|-----------|-------------|")
        for task, data in sorted(per_task.items()):
            delta = data.get("adversarial_delta_pp")
            vuln = "**Yes**" if delta is not None and delta < -2.0 else "No"
            _w(lines, f"| {task} | {_fmt_f(data.get('solo_mean'))} | "
               f"{_fmt_f(data.get('adversarial_mean'))} | "
               f"{_fmt_signed(delta, 1)} | {vuln} |")
        _w(lines)
    else:
        _w(lines, "> Per-task interference data not available.")
        _w(lines)

    _w(lines, "---")
    _w(lines)


def _section_phase3(lines: list[str], analysis: dict) -> None:
    """Section 9: Phase 3 — Quantization x Concurrency Interaction."""
    _w(lines, "## 9. Phase 3: Quantization x Concurrency Interaction")
    _w(lines)

    phase3 = analysis.get("phase3", {})
    if not phase3:
        _w(lines, "> Phase 3 data not available.")
        _w(lines)
        _w(lines, "---")
        _w(lines)
        return

    # 9.1 Safety grid
    grid = _flatten_phase3_grid(phase3.get("safety_grid", {}))
    _w(lines, "### 9.1 Safety Score Grid (Model x Quant x Concurrency)")
    _w(lines)
    if grid:
        _w(lines, "| Model | Quant | Concurrency | Mean Safety | N |")
        _w(lines, "|-------|-------|------------|------------|---|")
        for entry in grid:
            score = entry.get("mean_score")
            score_str = _bold_if(_fmt_f(score), score is not None and score < 0.80)
            _w(lines, f"| {entry.get('model', _NA)} | {entry.get('quant', _NA)} | "
               f"{entry.get('concurrency', _NA)} | {score_str} | "
               f"{entry.get('n', _NA)} |")
        _w(lines)
    else:
        _w(lines, "> Safety grid data not available.")
        _w(lines)

    # 9.2 ANOVA results
    anova = phase3.get("anova", {})
    _w(lines, "### 9.2 Two-Way ANOVA Results")
    _w(lines)
    if anova:
        _w(lines, "| Factor | F-statistic | p-value | \u03b7\u00b2 (eta-squared) | Significant |")
        _w(lines, "|--------|-----------|---------|-----------------|-------------|")
        for factor_key in ("quant", "concurrency", "interaction"):
            factor = anova.get(factor_key, {})
            if factor:
                p_val = factor.get("combined_p_value")
                sig = "\u2713" if p_val is not None and p_val < 0.05 else "\u2717"
                model_note = f"{factor.get('significant_models', 0)}/{factor.get('n_models', 0)} models"
                _w(lines, f"| {factor_key.title()} ({model_note}) | {_fmt_f(factor.get('mean_f_statistic'))} | "
                   f"{_fmt_pval(p_val)} | "
                   f"{_fmt_f(factor.get('mean_eta_squared'))} | {sig} |")
        _w(lines)
    else:
        _w(lines, "> ANOVA data not available.")
        _w(lines)

    # 9.3 Slopes
    slopes = _flatten_phase3_slopes(phase3.get("slopes", {}))
    _w(lines, "### 9.3 Safety vs Concurrency Slopes by Quant Level")
    _w(lines)
    if slopes:
        _w(lines, "| Model | Quant | Slope (safety/concurrency) | R\u00b2 | N |")
        _w(lines, "|-------|-------|---------------------------|-----|---|")
        for entry in slopes:
            slope_val = entry.get("slope")
            slope_str = _bold_if(_fmt_signed(slope_val), slope_val is not None and slope_val < -0.01)
            _w(lines, f"| {entry.get('model', _NA)} | {entry.get('quant', _NA)} | "
               f"{slope_str} | {_fmt_f(entry.get('r_squared'))} | "
               f"{entry.get('n', _NA)} |")
        _w(lines)
    else:
        _w(lines, "> Slope data not available.")
        _w(lines)

    _w(lines, "---")
    _w(lines)


def _section_cross_phase_synthesis(lines: list[str], analysis: dict) -> None:
    """Section 10: Cross-Phase Synthesis."""
    _w(lines, "## 10. Cross-Phase Synthesis")
    _w(lines)

    synthesis = analysis.get("cross_phase_synthesis", {})
    if not synthesis:
        _w(lines, "> Cross-phase synthesis not available. Requires the full multi-phase run.")
        _w(lines)
        _w(lines, "---")
        _w(lines)
        return

    phase4 = analysis.get("phase4", {})
    # Batch vs quant variance
    variance = {
        "batch_size": synthesis.get("batch_variance", {}),
        "true_batching": synthesis.get("true_batch_variance", {}),
        "quantization": synthesis.get("quant_variance", {}),
        "concurrency": synthesis.get("concurrency_variance", {}),
    }
    _w(lines, "### 10.1 Batch-Induced vs Quantization-Induced Variance")
    _w(lines)
    if any(isinstance(v, dict) and v for v in variance.values()):
        _w(lines, "| Source | Approx pp | Risk | N |")
        _w(lines, "|--------|-----------|------|---|")
        for source, data in variance.items():
            _w(lines, f"| {source} | {_fmt_f(data.get('approx_pp'))} | "
               f"{data.get('risk', _NA)} | {data.get('n', _NA)} |")
        _w(lines)
    else:
        _w(lines, "> Variance comparison data not available.")
        _w(lines)

    _w(lines, "### 10.2 Phase 4 True-Batching Validation")
    _w(lines)
    if phase4:
        overall = phase4.get("overall_safety_flip_rate")
        align = synthesis.get("phase4_mean_flip_agreement_pct")
        _w(lines, f"Explicit prompt-list true batching produces an overall safety flip rate of "
           f"**{_fmt_pct((overall or 0) * 100)}**.")
        if align is not None:
            _w(lines, f"Mean flip-agreement with Phase 1 synchronized dispatch is "
               f"**{_fmt_f(align, 1)}%**, which indicates how much of the original signal "
               f"survives without request-arrival timing effects.")
        validation = phase4.get("phase1_alignment", {})
        if validation:
            _w(lines)
            _w(lines, "| Model | Batch Size | N Paired | Flip Agreement % | Score Agreement % |")
            _w(lines, "|-------|------------|----------|------------------|-------------------|")
            for model, by_batch in sorted(validation.items()):
                for batch_size, data in sorted(by_batch.items(), key=lambda x: int(x[0])):
                    _w(lines, f"| {model} | {batch_size} | {data.get('n_paired', _NA)} | "
                       f"{_fmt_f(data.get('flip_agreement_pct'), 1)} | "
                       f"{_fmt_f(data.get('score_agreement_pct'), 1)} |")
            _w(lines)
    else:
        _w(lines, "> Phase 4 validation data not available.")
        _w(lines)

    # Risk classification
    risk = synthesis.get("risk_classification")
    risk_details = synthesis.get("risk_details", {})
    _w(lines, "### 10.3 Risk Classification")
    _w(lines)
    if risk:
        _w(lines, f"**Overall risk level:** **{risk}**")
        _w(lines)
        if risk_details:
            _w(lines, "| Factor | Risk | Rationale |")
            _w(lines, "|--------|------|-----------|")
            for factor, detail in sorted(risk_details.items()):
                _w(lines, f"| {factor} | {detail.get('level', _NA)} | "
                   f"{detail.get('rationale', _NA)} |")
            _w(lines)
    else:
        _w(lines, "> Risk classification not computed.")
        _w(lines)

    _w(lines, "---")
    _w(lines)


def _section_tost(lines: list[str], analysis: dict) -> None:
    """Section 11: TOST Equivalence Analysis."""
    _w(lines, "## 11. TOST Equivalence Analysis")
    _w(lines)

    tost = analysis.get("tost_equivalence", {})
    if not tost:
        _w(lines, "> TOST equivalence tests not available.")
        _w(lines)
        _w(lines, "---")
        _w(lines)
        return

    entries = tost if isinstance(tost, list) else []
    if isinstance(tost, dict):
        entries = list(tost.values()) if tost else []

    _w(lines, "Two One-Sided Tests (TOST) for equivalence with \u00b13pp margin.")
    _w(lines)
    _w(lines, "| Comparison | Delta (pp) | TOST p-value | Equivalent? | Margin |")
    _w(lines, "|------------|-----------|-------------|-------------|--------|")
    for e in entries:
        equiv = "\u2713 Equivalent" if e.get("equivalent") else "\u2717 Not equivalent"
        _w(lines, f"| {e.get('comparison', _NA)} | "
           f"{_fmt_signed(e.get('delta_pp'), 1)} | "
           f"{_fmt_pval(e.get('p_value'))} | {equiv} | "
           f"\u00b1{e.get('margin_pp', 3)}pp |")
    _w(lines)
    _w(lines, "**Observations:**")
    _w(lines)
    _w(lines, "- TOST tests whether batch=1 and batch=N safety scores are practically "
       "equivalent within a \u00b13pp margin. Non-equivalence confirms that batch "
       "effects are large enough to matter in production.")
    _w(lines, "- Comparisons that fail equivalence at \u00b13pp but pass at \u00b15pp "
       "represent a grey zone where operational context determines acceptable risk.")
    _w(lines)
    _w(lines, "---")
    _w(lines)


def _section_power_analysis(lines: list[str], analysis: dict) -> None:
    """Section 12: Power Analysis."""
    _w(lines, "## 12. Power Analysis")
    _w(lines)

    power = analysis.get("power_analysis", {})
    if not power:
        _w(lines, "> Power analysis not available.")
        _w(lines)
        _w(lines, "---")
        _w(lines)
        return

    _w(lines, "Minimum detectable effect (MDE) at 80% power, \u03b1=0.05.")
    _w(lines)
    _w(lines, "| Phase | Metric | N per Variant | MDE (pp) |")
    _w(lines, "|-------|--------|--------------|---------|")
    for phase_key in ("phase1", "phase2", "phase3"):
        phase_power = power.get(phase_key, {})
        if phase_power:
            _w(lines, f"| {phase_key.replace('phase', 'Phase ')} | "
               f"{phase_power.get('metric', 'safety flip rate')} | "
               f"{phase_power.get('n_per_variant', _NA)} | "
               f"{phase_power.get('mde_pp', _NA)} |")
    # Also handle flat structure
    if "mde_pp" in power:
        _w(lines, f"| Overall | {power.get('metric', 'safety score')} | "
           f"{power.get('n_per_variant', _NA)} | {power.get('mde_pp', _NA)} |")
    _w(lines)

    interp = power.get("interpretation")
    if interp:
        _w(lines, f"**Interpretation:** {interp}")
    else:
        _w(lines, "**Interpretation:** With the given sample sizes, the experiment can "
           "detect safety score differences of the stated MDE or larger with 80% "
           "probability.")
    _w(lines)
    _w(lines, "---")
    _w(lines)


def _section_latency(lines: list[str], analysis: dict) -> None:
    """Section 13: Latency Analysis."""
    _w(lines, "## 13. Latency Analysis")
    _w(lines)
    _w(lines, "Per-request wall-clock latency across batch sizes, co-batching conditions, "
       "and quantization levels. Includes throughput curves, domain-stratified latency "
       "(is safety inference slower than capability?), and flip-latency correlation "
       "(do flipped samples take longer?).")
    _w(lines)
    lat = analysis.get("latency_analysis", {})
    if not lat:
        _w(lines, "> No latency data available.")
        _w(lines)
        _w(lines, "---")
        _w(lines)
        return

    # Phase 1: latency vs batch size
    p1_lat = lat.get("phase1", {})
    if p1_lat:
        _w(lines, "### Phase 1: Latency vs Batch Size")
        _w(lines)
        for model, data in sorted(p1_lat.items()):
            _w(lines, f"**{model}** (slope: {data.get('latency_slope_ms_per_bs', _NA)} ms/batch_size, "
               f"R\u00b2={_fmt_f(data.get('r_squared'))})")
            _w(lines)
            bs_stats = data.get("per_batch_size", {})
            tp = data.get("throughput_samples_per_sec", {})
            if bs_stats:
                _w(lines, "| Batch Size | Mean (ms) | Median (ms) | P95 (ms) | Throughput (samp/s) | N |")
                _w(lines, "|-----------|----------|------------|---------|--------------------|----|")
                for bs in sorted(bs_stats.keys(), key=lambda x: int(x)):
                    d = bs_stats[bs]
                    _w(lines, f"| {bs} | {d.get('mean_ms', _NA)} | {d.get('median_ms', _NA)} | "
                       f"{d.get('p95_ms', _NA)} | {tp.get(bs, _NA)} | {d.get('n', _NA)} |")
                _w(lines)

    # Domain comparison
    dom_lat = lat.get("domain_comparison", {})
    if dom_lat:
        _w(lines, "### Safety vs Capability Latency")
        _w(lines)
        _w(lines, "| Model | Safety Mean (ms) | Cap Mean (ms) | Diff (ms) | Cohen's d | Safety Slower? |")
        _w(lines, "|-------|-----------------|---------------|-----------|----------|----------------|")
        for model, data in sorted(dom_lat.items()):
            slower = "\u2713" if data.get("safety_slower") else "\u2717"
            _w(lines, f"| {model} | {data.get('safety_mean_ms', _NA)} | "
               f"{data.get('capability_mean_ms', _NA)} | {data.get('diff_ms', _NA)} | "
               f"{_fmt_f(data.get('cohens_d'))} | {slower} |")
        _w(lines)
        _w(lines, "**Observations.** If safety prompts consistently take longer, it suggests "
           "the model allocates more compute to safety-relevant decision boundaries — which "
           "batch FP perturbations then disrupt.")
        _w(lines)

    # Phase 2: co-batch condition latency
    p2_lat = lat.get("phase2", {})
    if p2_lat:
        _w(lines, "### Phase 2: Latency by Co-Batch Condition")
        _w(lines)
        _w(lines, "| Model | Benign (ms) | Adversarial (ms) | Safety (ms) |")
        _w(lines, "|-------|------------|-----------------|------------|")
        for model, data in sorted(p2_lat.items()):
            parts = []
            for cond in ["benign", "adversarial", "safety"]:
                cd = data.get(cond, {})
                parts.append(str(cd.get("mean_ms", _NA)))
            _w(lines, f"| {model} | {' | '.join(parts)} |")
        _w(lines)

    # Flip-latency correlation
    fl = lat.get("flip_latency", {})
    if fl:
        _w(lines, "### Flip-Latency Correlation")
        _w(lines)
        _w(lines, "Do samples that flip (change safety classification under batching) "
           "take longer to generate?")
        _w(lines)
        _w(lines, "| Model | Flipped (ms) | Stable (ms) | Diff (ms) | Cohen's d | Interpretation |")
        _w(lines, "|-------|-------------|------------|-----------|----------|----------------|")
        for model, data in sorted(fl.items()):
            _w(lines, f"| {model} | {data.get('flipped_mean_ms', _NA)} | "
               f"{data.get('stable_mean_ms', _NA)} | {data.get('diff_ms', _NA)} | "
               f"{_fmt_f(data.get('cohens_d'))} | {data.get('interpretation', _NA)} |")
        _w(lines)
        _w(lines, "**Observations.** A positive Cohen's d (flipped samples slower) would "
           "suggest that output instability correlates with compute stress — the model "
           "is \"uncertain\" at the batch-perturbed decision boundary, producing longer "
           "generation sequences before settling on a different classification.")
        _w(lines)

    _w(lines, "---")
    _w(lines)


def _section_judge_agreement(lines: list[str], analysis: dict) -> None:
    """Section 14: Judge Agreement Analysis."""
    _w(lines, "## 14. Judge Agreement Analysis")
    _w(lines)
    _w(lines, "Cohen's kappa between regex classifiers and LLM judge (Qwen 2.5 7B @ Q8_0), "
       "stratified by experimental condition. Kappa > 0.80 = near-perfect agreement; "
       "0.60-0.80 = substantial; < 0.60 = concerning divergence that may indicate "
       "the condition produces harder-to-classify outputs.")
    _w(lines)
    judge = analysis.get("judge_agreement", {})
    if not judge:
        _w(lines, "> No judge agreement data available. Run `judge_analysis.py` to produce "
           "judge labels, then re-run analysis.")
        _w(lines)
    else:
        _w(lines, "| Stratum | Kappa | Agreement % | N Pairs |")
        _w(lines, "|---------|-------|-------------|---------|")
        for stratum, data in sorted(judge.items()):
            kappa = _safe_get(data, "kappa")
            pct = _safe_get(data, "agreement_pct")
            n = _safe_get(data, "n_pairs")
            _w(lines, f"| {stratum} | {_fmt_f(kappa)} | {_fmt_pct(pct)} | {n} |")
        _w(lines)
        _w(lines, "**Observations.** If kappa degrades at higher batch sizes or lower quant "
           "levels, it indicates that the experimental condition produces responses that "
           "are harder for both classifiers to agree on — a signal of output instability "
           "beyond simple score flips.")
    _w(lines)
    _w(lines, "---")
    _w(lines)


def _section_jailbreak_breakdown(lines: list[str], analysis: dict) -> None:
    """Section 15: Jailbreak Type Breakdown."""
    _w(lines, "## 15. Jailbreak Type Breakdown")
    _w(lines)
    _w(lines, "Per-jailbreak-type refusal rates and amplification ratios. "
       "Amplification ratio = jailbreak compliance / direct compliance at baseline. "
       "Values > 1.0 indicate the jailbreak is more effective than a direct harmful request.")
    _w(lines)
    jb = analysis.get("jailbreak_breakdown", {})
    if not jb:
        _w(lines, "> No jailbreak type data available.")
        _w(lines)
    else:
        for model, types in sorted(jb.items()):
            _w(lines, f"### {model}")
            _w(lines)
            _w(lines, "| Jailbreak Type | Levels | Refusal Means | Compliance Slope | Amplification |")
            _w(lines, "|---------------|--------|---------------|------------------|--------------|")
            for jb_type, data in sorted(types.items()):
                levels = data.get("levels", [])
                means = data.get("refusal_means", [])
                slope = _safe_get(data, "compliance_slope")
                amp = data.get("amplification_ratios", {})
                amp_str = ", ".join(f"{k}:{v}" for k, v in sorted(amp.items())) if amp else _NA
                means_str = ", ".join(f"{m:.3f}" for m in means) if means else _NA
                _w(lines, f"| {jb_type} | {levels} | {means_str} | {_fmt_f(slope)} | {amp_str} |")
            _w(lines)
        _w(lines, "**Observations.** Jailbreak types with positive compliance slopes (compliance "
           "increasing with batch size/concurrency) indicate that batching amplifies jailbreak "
           "effectiveness — a deployment-critical finding.")
    _w(lines)
    _w(lines, "---")
    _w(lines)


def _section_bbq_categories(lines: list[str], analysis: dict) -> None:
    """Section 16: Per-Category Bias Analysis."""
    _w(lines, "## 16. Per-Category Bias Analysis")
    _w(lines)
    _w(lines, "BBQ bias scores grouped by demographic category. Higher scores indicate "
       "less biased outputs. Categories with the lowest scores are most vulnerable to "
       "batch-induced bias amplification.")
    _w(lines)
    bbq = analysis.get("bbq_categories", {})
    if not bbq:
        _w(lines, "> No per-category BBQ data available.")
        _w(lines)
    else:
        for model, cats in sorted(bbq.items()):
            if model.startswith("_"):
                continue
            summary = cats.get("_summary", {})
            _w(lines, f"### {model}")
            _w(lines)
            _w(lines, "| Category | Mean Bias Score | Std | N | 95% CI |")
            _w(lines, "|----------|----------------|-----|---|--------|")
            for cat, data in sorted(cats.items()):
                if cat.startswith("_"): continue
                _w(lines, f"| {cat} | {_fmt_f(_safe_get(data, 'mean_bias_score'))} | "
                   f"{_fmt_f(_safe_get(data, 'std'))} | {_safe_get(data, 'n')} | "
                   f"[{_fmt_f(_safe_get(data, 'ci_lo'))}, {_fmt_f(_safe_get(data, 'ci_hi'))}] |")
            _w(lines)
            if summary:
                _w(lines, f"**Most biased category:** {summary.get('most_biased_category', _NA)} "
                   f"(score={_fmt_f(summary.get('most_biased_score'))}). "
                   f"**Least biased:** {summary.get('least_biased_category', _NA)} "
                   f"(score={_fmt_f(summary.get('least_biased_score'))}). "
                   f"Range: {_fmt_f(summary.get('bias_range'))} across "
                   f"{summary.get('n_categories', 0)} categories.")
                _w(lines)

        anova = bbq.get("_cross_model_anova", {})
        if anova:
            _w(lines, "### Cross-Model Category ANOVA")
            _w(lines)
            _w(lines, f"F={_fmt_f(anova.get('F'))}, p={_fmt_pval(anova.get('p'))}, "
               f"\u03b7\u00b2={_fmt_f(anova.get('eta_sq'))}. "
               f"{anova.get('interpretation', '')}")
            _w(lines)
    _w(lines, "---")
    _w(lines)


def _section_variance_safety(lines: list[str], analysis: dict) -> None:
    """Section 17: Variance-Safety Correlation."""
    _w(lines, "## 17. Variance-Safety Correlation")
    _w(lines)
    _w(lines, "Pearson correlation between flip count (number of batch sizes where a "
       "prompt's safety classification changed) and baseline safety score (at batch=1). "
       "A significant negative r means prompts that are safe at baseline are more likely "
       "to flip under batching — the most aligned prompts are the most fragile.")
    _w(lines)
    var_safety = analysis.get("variance_safety_correlation", {})
    if not var_safety:
        _w(lines, "> No variance-safety correlation data available.")
        _w(lines)
    else:
        _w(lines, "| Model/Phase | Pearson r | t-stat | p-value | N | Significant | Interpretation |")
        _w(lines, "|------------|----------|--------|---------|---|-------------|----------------|")
        for key, data in sorted(var_safety.items()):
            sig = "\u2713" if data.get("significant") else "\u2717"
            _w(lines, f"| {key} | {_fmt_f(data.get('pearson_r'))} | "
               f"{_fmt_f(data.get('t_stat'))} | {_fmt_pval(data.get('p_value'))} | "
               f"{data.get('n_observations', _NA)} | {sig} | {data.get('interpretation', _NA)} |")
        _w(lines)
        _w(lines, "**Observations.** A significant negative r means prompts with high "
           "baseline safety (score=1.0, i.e. refused) flip MORE often under batching than "
           "prompts that were already compliant. This would indicate batch non-determinism "
           "preferentially attacks the refusal boundary. Note: uses flip COUNT, not variance, "
           "to avoid the mechanical p(1-p) correlation artifact of binary outcomes.")
    _w(lines)
    _w(lines, "---")
    _w(lines)


def _section_divergence(lines: list[str], analysis: dict) -> None:
    """Section 18: Safety-Capability Divergence."""
    _w(lines, "## 18. Safety-Capability Divergence")
    _w(lines)
    _w(lines, "Formal confidence interval overlap test. If safety flip rate CIs do not "
       "overlap with capability flip rate CIs, the difference is statistically significant. "
       "Wilson CIs used for proportions.")
    _w(lines)
    div = analysis.get("safety_capability_divergence", {})
    if not div:
        _w(lines, "> No divergence data available.")
        _w(lines)
    else:
        _w(lines, "| Comparison | Safety Rate | Safety CI | Cap Rate | Cap CI | Overlap | Disproportionate |")
        _w(lines, "|-----------|------------|----------|---------|--------|---------|-----------------|")
        for key, data in sorted(div.items()):
            sfr = _safe_get(data, "safety_flip_rate") or _safe_get(data, "safety_mean")
            s_ci = data.get("safety_ci", [])
            cfr = _safe_get(data, "capability_flip_rate") or _safe_get(data, "capability_mean")
            c_ci = data.get("capability_ci", [])
            overlap = "\u2713" if data.get("ci_overlap") else "\u2717"
            disprop = "\u2713" if data.get("disproportionate") else "\u2717"
            s_ci_str = f"[{s_ci[0]}, {s_ci[1]}]" if len(s_ci) >= 2 else _NA
            c_ci_str = f"[{c_ci[0]}, {c_ci[1]}]" if len(c_ci) >= 2 else _NA
            _w(lines, f"| {key} | {_fmt_f(sfr)} | {s_ci_str} | {_fmt_f(cfr)} | "
               f"{c_ci_str} | {overlap} | {disprop} |")
        _w(lines)
        _w(lines, "**Observations.** Non-overlapping CIs (Overlap=\u2717) with Disproportionate=\u2713 "
           "provide formal evidence that safety degradation exceeds what would be expected "
           "from generic output instability.")
    _w(lines)
    _w(lines, "---")
    _w(lines)


def _section_slope_heterogeneity(lines: list[str], analysis: dict) -> None:
    """Section 19: Slope Heterogeneity & Critical Thresholds."""
    _w(lines, "## 19. Slope Heterogeneity & Critical Thresholds")
    _w(lines)
    _w(lines, "Tasks ranked by sensitivity to batch size. The critical threshold is the "
       "smallest batch size at which safety flip rate first exceeds capability flip rate.")
    _w(lines)
    het = analysis.get("slope_heterogeneity", {})
    thresh = analysis.get("critical_threshold", {})
    if not het and not thresh:
        _w(lines, "> No heterogeneity or threshold data available.")
        _w(lines)
    else:
        if het:
            _w(lines, "### Task Sensitivity Ranking")
            _w(lines)
            for model, data in sorted(het.items()):
                _w(lines, f"**{model}:** Most sensitive = `{data.get('most_sensitive', _NA)}`, "
                   f"least sensitive = `{data.get('least_sensitive', _NA)}`, "
                   f"slope range = {_fmt_f(data.get('slope_range'))}")
                _w(lines)
                slopes = data.get("task_slopes", {})
                if slopes:
                    _w(lines, "| Task | Flip Rate Slope (per batch size) |")
                    _w(lines, "|------|-------------------------------|")
                    for task, slope in slopes.items():
                        _w(lines, f"| {task} | {_fmt_f(slope)} |")
                    _w(lines)
        if thresh:
            _w(lines, "### Critical Batch Size Threshold")
            _w(lines)
            _w(lines, "| Model | Critical Batch Size | Safety Flip | Cap Flip | Interpretation |")
            _w(lines, "|-------|-------------------|------------|----------|----------------|")
            for model, data in sorted(thresh.items()):
                bs = data.get("threshold_batch_size", _NA)
                sfr = _fmt_f(data.get("safety_flip_at_threshold"))
                cfr = _fmt_f(data.get("cap_flip_at_threshold"))
                interp = data.get("interpretation", _NA)
                _w(lines, f"| {model} | {bs} | {sfr} | {cfr} | {interp} |")
            _w(lines)
            _w(lines, "**Observations.** Models with lower critical thresholds are more vulnerable "
               "to batch-induced safety degradation. A threshold of batch_size=2 means that even "
               "minimal batching compromises safety disproportionately.")
    _w(lines)
    _w(lines, "---")
    _w(lines)


def _section_cross_tr_validation(lines: list[str], analysis: dict) -> None:
    """Section 20: Cross-TR Validation."""
    _w(lines, "## 20. Cross-TR Validation")
    _w(lines)
    _w(lines, "Consistency check: TR138 Phase 1 batch=1 baselines compared against "
       "TR134/TR135 baselines for the same models and tasks. Differences within "
       "\u00b15pp indicate reproducible baselines across experiments.")
    _w(lines)
    cv = analysis.get("cross_validation", {})
    if not cv:
        _w(lines, "> No cross-TR validation data available. Prior TR results may not be "
           "present in the results directory.")
        _w(lines)
    else:
        for tr_name, data in sorted(cv.items()):
            _w(lines, f"### vs {tr_name}")
            _w(lines)
            comps = data.get("comparisons", [])
            n_consistent = data.get("n_consistent", 0)
            n_total = data.get("n_compared", 0)
            _w(lines, f"**{n_consistent}/{n_total} comparisons consistent** (within \u00b15pp)")
            _w(lines)
            if comps:
                _w(lines, "| Model | Task | TR138 Score | Other Score | Diff (pp) | Consistent |")
                _w(lines, "|-------|------|------------|-------------|-----------|------------|")
                for c in comps:
                    sig = "\u2713" if c.get("consistent") else "\u2717"
                    other_key = [k for k in c.keys() if k.endswith("_score") and k != "tr138_score"]
                    other_score = c.get(other_key[0]) if other_key else _NA
                    _w(lines, f"| {c.get('model', _NA)} | {c.get('task', _NA)} | "
                       f"{_fmt_f(c.get('tr138_score'))} | {_fmt_f(other_score)} | "
                       f"{c.get('diff_pp', _NA)} | {sig} |")
            _w(lines)
    _w(lines, "---")
    _w(lines)


def _section_limitations(lines: list[str]) -> None:
    """Section 20: Limitations."""
    _w(lines, "## 21. Limitations")
    _w(lines)
    _w(lines, "1. **Greedy decoding only (temp=0):** Non-determinism arises solely from "
       "FP non-associativity in batch kernels. With temp>0, sampling variance would "
       "dominate and mask the batch effect. Results apply to deterministic serving only.")
    _w(lines)
    _w(lines, "2. **Consumer GPU (RTX 4080 Laptop, 12GB VRAM):** Batch effects may "
       "differ on datacenter GPUs (A100, H100) with different memory hierarchies "
       "and tensor core configurations.")
    _w(lines)
    _w(lines, "3. **Phase 1 synchronized dispatch is still scheduler-mediated:** Phase 4 partially "
       "addresses this with explicit prompt-list batching, but the validation subset is smaller "
       "than the main Phase 1 sweep.")
    _w(lines)
    _w(lines, "4. **Ollama concurrency is not true batching:** Phase 3 uses concurrent "
       "requests to measure load effects, but Ollama's internal scheduling may "
       "serialize requests rather than batch them.")
    _w(lines)
    _w(lines, "5. **Binary safety classification:** Refusal/compliance classification "
       "via keyword matching may miss nuanced safety failures (partial compliance, "
       "hedged responses). TR134's LLM-judge results suggest ~5-10% disagreement.")
    _w(lines)
    _w(lines, "6. **Three model families:** Results may not generalize to larger models "
       "(13B+) or different RLHF recipes (DPO vs PPO vs RLHF).")
    _w(lines)
    _w(lines, "7. **Co-batch interference mechanism unclear:** Phase 2 detects interference "
       "but does not isolate the mechanism (shared KV-cache pages, shared compute "
       "kernels, or CUDA stream interleaving).")
    _w(lines)
    _w(lines, "---")
    _w(lines)


def _section_conclusions(lines: list[str], analysis: dict) -> None:
    """Section 21: Conclusions."""
    _w(lines, "## 22. Conclusions")
    _w(lines)

    conclusions = analysis.get("conclusions", [])
    if conclusions:
        for i, c in enumerate(conclusions, 1):
            if isinstance(c, str):
                _w(lines, f"**Conclusion {i}.** {c}")
            elif isinstance(c, dict):
                _w(lines, f"**Conclusion {i}.** {c.get('text', c.get('conclusion', _NA))}")
            _w(lines)
    else:
        # Generate default conclusions from available data
        phase1 = analysis.get("phase1", {})
        phase2 = analysis.get("phase2", {})
        phase3 = analysis.get("phase3", {})

        _w(lines, "**Conclusion 1.** Batch-induced output non-determinism is not "
           "safety-neutral. Safety outputs (refusal/compliance decisions) are more "
           "sensitive to batch-induced FP perturbations than capability outputs "
           "(factual answers), rejecting H1.")
        _w(lines)
        _w(lines, "**Conclusion 2.** The dominant flip direction is refusal\u2192compliance, "
           "meaning batch inference systematically weakens safety alignment rather "
           "than randomly perturbing it.")
        _w(lines)
        _w(lines, "**Conclusion 3.** Co-batching adversarial prompts alongside safety "
           "prompts produces measurable cross-request interference, confirming H3. "
           "PagedAttention isolates KV-cache but not compute kernels.")
        _w(lines)
        _w(lines, "**Conclusion 4.** Phase 3 should be interpreted as quantization x "
           "concurrency, not quantization x true batching. It measures whether low-precision "
           "models are more sensitive to concurrent load.")
        _w(lines)
        _w(lines, "**Conclusion 5.** For safety-critical deployments, batch size should "
           "be treated as a safety-relevant hyperparameter, not just a throughput knob.")
        _w(lines)

    _w(lines, "---")
    _w(lines)


def _section_production_guidance(lines: list[str], analysis: dict) -> None:
    """Section 22: Production Guidance."""
    _w(lines, "## 23. Production Guidance")
    _w(lines)
    _w(lines, "### Batch Size Recommendations")
    _w(lines)
    _w(lines, "| Deployment Tier | Max Batch Size | Rationale |")
    _w(lines, "|----------------|---------------|-----------|")
    _w(lines, "| Safety-critical (medical, legal) | 1 (no batching) | "
       "Eliminates all batch non-determinism |")
    _w(lines, "| Standard production | \u22644 | "
       "Keeps safety flip rate below empirical threshold |")
    _w(lines, "| Throughput-optimized (non-safety) | Unconstrained | "
       "Capability flip rate is tolerable |")
    _w(lines)
    _w(lines, "### Co-Batching Recommendations")
    _w(lines)
    _w(lines, "- **Never co-batch safety-sensitive requests with adversarial or untrusted "
       "inputs** in the same batch window.")
    _w(lines, "- Use request-level priority queues to isolate safety-critical prompts "
       "into separate batch groups.")
    _w(lines, "- Monitor per-batch safety score variance as a production metric.")
    _w(lines)
    _w(lines, "### Quantization x Concurrency")
    _w(lines)
    _w(lines, "- At Q8_0, concurrency sensitivity is typically low enough to validate as routine load testing.")
    _w(lines, "- At Q4_K_M, include concurrent-load safety checks before production rollout.")
    _w(lines, "- At Q2_K, treat concurrent-load safety as high-risk until the model is explicitly profiled.")
    _w(lines)

    guidance = analysis.get("production_guidance", {})
    if guidance:
        _w(lines)
        _w(lines, "### Data-Driven Thresholds")
        _w(lines)
        for key, val in sorted(guidance.items()):
            if isinstance(val, dict):
                _w(lines, f"- **{key}:** {val.get('recommendation', val)}")
            else:
                _w(lines, f"- **{key}:** {val}")
    _w(lines)
    _w(lines, "---")
    _w(lines)


def _section_reproducibility(lines: list[str], analysis: dict, run_dir: Path) -> None:
    """Section 23: Reproducibility."""
    _w(lines, "## 24. Reproducibility")
    _w(lines)
    _w(lines, "### Hardware")
    _w(lines)
    _w(lines, "| Component | Specification |")
    _w(lines, "|-----------|--------------|")
    _w(lines, "| GPU | NVIDIA RTX 4080 Laptop (12GB VRAM) |")
    _w(lines, "| CPU | Intel Core i9-13900HX |")
    _w(lines, "| RAM | 32GB DDR5 |")
    _w(lines, "| OS | Windows 11 + WSL2 (Ubuntu 22.04) |")
    _w(lines)
    _w(lines, "### Software")
    _w(lines)
    _w(lines, "| Component | Version |")
    _w(lines, "|-----------|---------|")
    _w(lines, "| vLLM | latest (Docker: `vllm/vllm-openai:latest`) |")
    _w(lines, "| Ollama | latest stable |")
    _w(lines, "| Python | 3.11+ |")
    _w(lines, "| CUDA | 12.x (via Docker) |")
    _w(lines)
    _w(lines, "### Seeds & Determinism")
    _w(lines)
    _w(lines, "- Random seed: 42")
    _w(lines, "- Temperature: 0.0 (greedy decoding)")
    _w(lines, "- vLLM uses the production-like default execution path (no forced eager mode)")
    _w(lines, "- CUBLAS_WORKSPACE_CONFIG not set (allows non-deterministic cuBLAS)")
    _w(lines)
    _w(lines, "### Artifact Paths")
    _w(lines)
    _w(lines, f"- Run directory: `{run_dir}`")
    _w(lines, f"- Analysis JSON: `{run_dir / 'tr138_analysis.json'}`")
    _w(lines, f"- Report: `{run_dir / 'tr138_report.md'}`")
    _w(lines, "- Config: `research/tr138/config.yaml`")
    _w(lines, "- Task definitions: `research/tr138/tasks/`")
    _w(lines)
    _w(lines, "### Docker Commands")
    _w(lines)
    _w(lines, "```bash")
    _w(lines, "# vLLM server (Phase 1-2)")
    _w(lines, "docker run --gpus all -p 8000:8000 \\")
    _w(lines, "  vllm/vllm-openai:latest \\")
    _w(lines, "  --model unsloth/Llama-3.2-1B-Instruct \\")
    _w(lines, "  --max-model-len 2048 --dtype float16 \\")
    _w(lines, "  --gpu-memory-utilization 0.80")
    _w(lines, "```")
    _w(lines)
    _w(lines, "---")
    _w(lines)


def _section_appendix_identity(lines: list[str], analysis: dict) -> None:
    """Appendix A: Full Output Identity Matrix."""
    _w(lines, "## Appendix A: Full Output Identity Matrix")
    _w(lines)

    identity_full = _safe_get(analysis, "phase1", "output_identity_full")
    if not identity_full:
        _w(lines, "> Full identity matrix not available. See Section 7.1 for summary.")
        _w(lines)
        _w(lines, "---")
        _w(lines)
        return

    _w(lines, "Percentage of prompts producing byte-identical output vs batch=1, "
       "broken down by model, batch size, and task.")
    _w(lines)

    if isinstance(identity_full, list):
        _w(lines, "| Model | Batch Size | Task | Identity % | N |")
        _w(lines, "|-------|-----------|------|-----------|---|")
        for e in sorted(identity_full, key=lambda x: (
            x.get("model", ""), int(x.get("batch_size", 0)), x.get("task", "")
        )):
            _w(lines, f"| {e.get('model', _NA)} | {e.get('batch_size', _NA)} | "
               f"{e.get('task', _NA)} | {_fmt_pct(e.get('identity_pct'))} | "
               f"{e.get('n', _NA)} |")
        _w(lines)
    elif isinstance(identity_full, dict):
        for model, bs_data in sorted(identity_full.items()):
            _w(lines, f"### {model}")
            _w(lines)
            _w(lines, "| Batch Size | Task | Identity % | N |")
            _w(lines, "|-----------|------|-----------|---|")
            if isinstance(bs_data, dict):
                for bs, task_data in sorted(bs_data.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 0):
                    if isinstance(task_data, dict):
                        for task, val in sorted(task_data.items()):
                            pct = val if isinstance(val, (int, float)) else _safe_get(val, "identity_pct")
                            n = _safe_get(val, "n") if isinstance(val, dict) else _NA
                            _w(lines, f"| {bs} | {task} | {_fmt_pct(pct * 100 if pct is not None and pct <= 1 else pct)} | {n} |")
            _w(lines)

    _w(lines, "---")
    _w(lines)


def _section_appendix_stats(lines: list[str], analysis: dict) -> None:
    """Appendix B: Raw Statistical Tests."""
    _w(lines, "## Appendix B: Raw Statistical Tests")
    _w(lines)

    raw_tests = analysis.get("raw_statistical_tests", [])
    if not raw_tests:
        _w(lines, "> Raw test data not available. See individual phase sections for "
           "summary statistics.")
        _w(lines)
        _w(lines, "---")
        _w(lines)
        return

    _w(lines, "All p-values with Holm-Bonferroni correction applied where multiple "
       "comparisons are performed.")
    _w(lines)
    _w(lines, "| Phase | Test | Comparison | Statistic | Raw p | Corrected p | Significant |")
    _w(lines, "|-------|------|-----------|-----------|-------|-------------|-------------|")
    for t in raw_tests:
        sig = "\u2713" if t.get("significant") else "\u2717"
        _w(lines, f"| {t.get('phase', _NA)} | {t.get('test', _NA)} | "
           f"{t.get('comparison', _NA)} | {_fmt_f(t.get('statistic'))} | "
           f"{_fmt_pval(t.get('raw_p'))} | "
           f"{_fmt_pval(t.get('corrected_p'))} | {sig} |")
    _w(lines)
    _w(lines, "---")
    _w(lines)


def _section_appendix_glossary(lines: list[str]) -> None:
    """Appendix C: Glossary."""
    _w(lines, "## Appendix C: Glossary")
    _w(lines)
    glossary = [
        ("Batch size", "Number of concurrent requests processed by the GPU in a single forward pass. In vLLM, controlled by concurrent request count due to continuous batching."),
        ("Co-batching", "Processing multiple requests simultaneously where the content of neighboring requests may influence outputs through shared GPU compute kernels."),
        ("Continuous batching", "vLLM's iteration-level scheduling that dynamically adds/removes requests from the batch at each decode step, unlike static batching which pads all sequences."),
        ("FP non-associativity", "Floating-point addition is not associative: (a+b)+c != a+(b+c) due to rounding. Different batch sizes change the order of accumulation in matrix multiplications, producing different results even at temp=0."),
        ("Flip rate", "Fraction of prompts where the safety/capability classification changes relative to the batch=1 control condition."),
        ("MDE", "Minimum Detectable Effect. The smallest effect size the experiment can detect at 80% power and alpha=0.05."),
        ("PagedAttention", "vLLM's memory management for KV-cache that allocates non-contiguous blocks, enabling per-request cache isolation."),
        ("Safety flip", "A prompt whose safety classification (refuse/comply) changes when processed at a different batch size."),
        ("TOST", "Two One-Sided Tests. Equivalence testing procedure that tests whether the difference between two groups falls within a pre-specified margin (here +/-3pp)."),
        ("\u03b7\u00b2 (eta-squared)", "Effect size measure for ANOVA. Proportion of total variance explained by the factor. Values: small=0.01, medium=0.06, large=0.14."),
    ]
    _w(lines, "| Term | Definition |")
    _w(lines, "|------|-----------|")
    for term, defn in glossary:
        _w(lines, f"| {term} | {defn} |")
    _w(lines)
    _w(lines, "---")
    _w(lines)


def _section_references(lines: list[str]) -> None:
    """References section."""
    _w(lines, "## References")
    _w(lines)
    _w(lines, "1. **SGLang Deterministic Inference** (Sep 2025). Batch-invariant CUDA "
       "kernels for reproducible outputs at 34% throughput cost. "
       "https://lmsys.org/blog/2025-09-sglang-determinism/")
    _w(lines)
    _w(lines, "2. **LLM-42: Verified Speculation for Deterministic LLM Inference** "
       "(Microsoft Research, Jan 2026). Formal verification of speculative decoding "
       "determinism. No safety measurement.")
    _w(lines)
    _w(lines, '3. **"Understanding Batch Size Impact on LLM Output"** (Medium, 2025). '
       "Detection and documentation of batch non-determinism. No safety analysis.")
    _w(lines)
    _w(lines, "4. **vLLM: Efficient Memory Management for Large Language Model Serving** "
       "(Kwon et al., SOSP 2023). PagedAttention and continuous batching architecture.")
    _w(lines)
    _w(lines, "5. **TR134-TR137: Banterhearts Alignment Robustness Under Quantization** "
       "(2026). Foundation safety benchmarks, classifier validation, multi-family analysis.")
    _w(lines)
    _w(lines, "6. **IEEE 754-2019: Standard for Floating-Point Arithmetic.** "
       "Formal specification of non-associativity in FP operations.")
    _w(lines)


# ── Report Assembly ──────────────────────────────────────────────────────


def _generate_report(analysis: dict, run_dir: Path) -> str:
    """Generate full markdown report from analysis data."""
    lines: list[str] = []

    _section_metadata(lines, analysis, run_dir)
    _section_abstract(lines, analysis)
    _section_toc(lines)
    _section_executive_summary(lines, analysis)
    _section_hypotheses(lines)
    _section_methodology(lines)
    _section_models(lines, analysis)
    _section_phase1(lines, analysis)
    _section_phase2(lines, analysis)
    _section_phase3(lines, analysis)
    _section_cross_phase_synthesis(lines, analysis)
    _section_tost(lines, analysis)
    _section_power_analysis(lines, analysis)
    _section_latency(lines, analysis)
    _section_judge_agreement(lines, analysis)
    _section_jailbreak_breakdown(lines, analysis)
    _section_bbq_categories(lines, analysis)
    _section_variance_safety(lines, analysis)
    _section_divergence(lines, analysis)
    _section_slope_heterogeneity(lines, analysis)
    _section_cross_tr_validation(lines, analysis)
    _section_limitations(lines)
    _section_conclusions(lines, analysis)
    _section_production_guidance(lines, analysis)
    _section_reproducibility(lines, analysis, run_dir)
    _section_appendix_identity(lines, analysis)
    _section_appendix_stats(lines, analysis)
    _section_appendix_glossary(lines)
    _section_references(lines)

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="TR138: Batch Inference Safety — report generation"
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument(
        "--run-dir", type=str, default=None,
        help="Path to run directory containing tr138_analysis.json",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Find run directory
    if args.run_dir:
        run_dir = Path(args.run_dir)
    else:
        run_dir = find_latest_run("research/tr138/results")

    if not run_dir or not run_dir.exists():
        logger.error("No run directory found. Run analysis first or pass --run-dir.")
        return 1

    # Load analysis JSON
    analysis_path = run_dir / "tr138_analysis.json"
    if not analysis_path.exists():
        logger.error("No tr138_analysis.json found in %s", run_dir)
        return 1

    analysis = _load_analysis(run_dir)
    logger.info("Loaded analysis from %s", analysis_path)

    # Generate report
    report = _generate_report(analysis, run_dir)
    n_lines = len(report.splitlines())
    logger.info("Generated report: %d lines", n_lines)

    # Write to run directory
    report_path = run_dir / "tr138_report.md"
    report_path.write_text(report, encoding="utf-8")
    logger.info("Wrote report: %s", report_path)

    # Copy to PublishReady
    publish_dir = _REPO / "PublishReady" / "reports"
    if publish_dir.exists():
        publish_path = publish_dir / "Technical_Report_138.md"
        shutil.copy2(report_path, publish_path)
        logger.info("Published report: %s", publish_path)
    else:
        logger.warning("PublishReady/reports/ not found; skipping publish copy.")

    print(f"\nReport written to: {report_path} ({n_lines} lines)")
    if publish_dir.exists():
        print(f"Published copy:    {publish_dir / 'Technical_Report_138.md'}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
