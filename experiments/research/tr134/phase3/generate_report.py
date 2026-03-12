"""TR134 Phase 3: Generate comprehensive 18-section multi-family alignment report.

Reads phase3_analysis.json and produces a full markdown report covering
multi-family degradation curves, per-category bias, jailbreak amplification,
LLM judge agreement, and cross-family comparison.

Report structure (18 sections):
  Header — data counts, model families, task listing
  1.  Executive Summary — 8 numbered findings
  2.  Degradation Curves (Safety) — per-model tables with CI
  3.  Degradation Curves (Capability) — per-model tables with CI
  4.  Slope Analysis — full regression table
  5.  Safety vs Capability Comparison — per-model divergence
  6.  Per-Benchmark Breakdown — per-task model×quant tables
  7.  Critical Thresholds — per-quant safety/capability ratios
  8.  Statistical Tests (Pairwise) — significant results by domain
  9.  Power Analysis — MDE table and interpretation
  10. Cross-Phase Validation — Phase 2 vs Phase 3 consistency
  11. Per-Quant Safety/Capability Ratio — detailed ratio table
  12. Methodology (base sections)
  13. Per-Category Bias Analysis — NEW
  14. Jailbreak Amplification Results — NEW
  15. LLM Judge Agreement — NEW
  16. Cross-Family Comparison — NEW
  17. Multi-Family Slope Comparison — NEW
  18. Updated Methodology & Limitations — NEW (extended)

Usage:
    python research/tr134/phase3/generate_report.py [-v] [--run-dir PATH]
"""

from __future__ import annotations

import argparse
import json
import logging
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
import sys

_DIR = Path(__file__).resolve().parent
_REPO = _DIR.parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from research.tr125.shared.utils import QUANT_BPW, QUANT_PRECISION_ORDER
from research.tr134.shared.utils import TR134_7B_MODELS, find_latest_run

logger = logging.getLogger("tr134.phase3.generate_report")


def _sort_quant(quant: str) -> int:
    try:
        return QUANT_PRECISION_ORDER.index(quant)
    except ValueError:
        return len(QUANT_PRECISION_ORDER)


def _w(lines: list[str], text: str = "") -> None:
    lines.append(text)


def _fmt_ci(ci_lo: float | None, ci_hi: float | None) -> str:
    if ci_lo is None or ci_hi is None:
        return "---"
    return f"[{ci_lo:.3f}, {ci_hi:.3f}]"


# ── Section Builders ────────────────────────────────────────────────────────


def _section_header(lines: list[str], analysis: dict[str, Any], run_dir: Path) -> None:
    metadata = analysis.get("metadata", {})
    total = metadata.get("total_records", 0)
    safety_n = metadata.get("safety_records", 0)
    cap_n = metadata.get("capability_records", 0)
    n_models = metadata.get("n_models", 0)
    n_quants = metadata.get("n_quants", 0)
    safety_tasks = metadata.get("safety_tasks", [])
    capability_tasks = metadata.get("capability_tasks", [])

    _w(lines, "# TR134: Multi-Family Alignment Robustness Under Quantization — Phase 3 Report")
    _w(lines)
    _w(lines, f"**Generated:** {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}")
    _w(lines, f"**Run directory:** `{run_dir.name}`")
    _w(lines)
    _w(lines, "| Metric | Value |")
    _w(lines, "|--------|-------|")
    _w(lines, f"| Total samples | {total:,} |")
    _w(lines, f"| Safety samples | {safety_n:,} |")
    _w(lines, f"| Capability samples | {cap_n:,} |")
    _w(lines, f"| Model families | {n_models} |")
    _w(lines, f"| Quantization levels | {n_quants} |")
    _w(lines)
    _w(lines, f"**Safety tasks:** {', '.join(sorted(safety_tasks)) or 'N/A'}")
    _w(lines, f"**Capability tasks:** {', '.join(sorted(capability_tasks)) or 'N/A'}")
    _w(lines)
    _w(lines, "**Model families:** Llama 3.2 (1B, 3B), Mistral (7B), Qwen 2.5 (7B)")
    _w(lines)
    _w(lines, "**Research questions:**")
    _w(lines, "1. Is safety degradation under quantization universal or RLHF-recipe-specific?")
    _w(lines, "2. Do regex classifiers miss important safety failures at low quant?")
    _w(lines, "3. Which demographic categories are most vulnerable to quantization-induced bias?")
    _w(lines, "4. Does quantization amplify jailbreak susceptibility?")
    _w(lines, "5. At what quantization level does safety degrade disproportionately to capability?")
    _w(lines)
    _w(lines, "---")
    _w(lines)


def _section_executive_summary(lines: list[str], analysis: dict[str, Any]) -> None:
    _w(lines, "## 1. Executive Summary")
    _w(lines)

    comparisons = analysis.get("slope_comparisons", {})
    thresholds = analysis.get("critical_thresholds", {})
    family_cmp = analysis.get("family_comparison", {})
    jailbreak = analysis.get("jailbreak_amplification", {})
    judge = analysis.get("judge_agreement", {})
    per_cat = analysis.get("per_category_bias", {})
    group_stats = analysis.get("group_stats", {})
    power = analysis.get("power_analysis", {})

    # Finding 1 — Overall verdict
    any_significant = any(
        c.get("conclusion", "").startswith("SIGNIFICANT") for c in comparisons.values()
    )
    any_divergence = any(c.get("safety_degrades_faster", False) for c in comparisons.values())
    n_models_degrading = sum(1 for c in comparisons.values() if c.get("safety_degrades_faster"))
    if any_significant:
        _w(lines, f"**Finding 1 — Overall Verdict:** {n_models_degrading}/{len(comparisons)} models "
           "show safety degrading faster than capability (CIs non-overlapping). "
           "**RLHF safety veneer hypothesis SUPPORTED.**")
    elif any_divergence:
        _w(lines, f"**Finding 1 — Overall Verdict:** {n_models_degrading}/{len(comparisons)} models "
           "show steeper safety slopes but CIs overlap. **Weakly supported.**")
    else:
        _w(lines, "**Finding 1 — Overall Verdict:** Safety is as robust as capability "
           "under quantization. **Not supported.**")
    _w(lines)

    # Finding 2 — Cross-family
    if family_cmp.get("available"):
        p_val = family_cmp.get("p_value")
        _w(lines, f"**Finding 2 — Cross-Family:** {family_cmp['conclusion']} "
           f"(F={family_cmp['f_statistic']:.2f}, p={'<0.001' if p_val and p_val < 0.001 else f'{p_val:.4f}' if p_val else 'N/A'}).")
    else:
        _w(lines, "**Finding 2 — Cross-Family:** Insufficient data for comparison.")
    _w(lines)

    # Finding 3 — Worst safety drop
    safety_entries = [
        d for d in group_stats.values()
        if d.get("domain") == "safety" and d.get("delta_pp") is not None
        and d.get("quant") not in ("FP16", "Q8_0") or (
            d.get("quant") == "Q8_0" and d.get("base_model") not in TR134_7B_MODELS
        )
    ]
    if safety_entries:
        worst = min(safety_entries, key=lambda d: d.get("delta_pp", 0))
        _w(lines, f"**Finding 3 — Worst Safety Drop:** {worst['base_model']} x "
           f"{worst['quant']} ({worst['metric']}) loses **{worst['delta_pp']:+.1f}pp** vs baseline.")
    _w(lines)

    # Finding 4 — Jailbreak amplification
    if jailbreak.get("available"):
        jb_slopes = jailbreak.get("jailbreak_slopes", {})
        if jb_slopes:
            worst_jb = min(jb_slopes.items(), key=lambda kv: kv[1])
            _w(lines, f"**Finding 4 — Jailbreak Amplification:** "
               f"'{worst_jb[0]}' jailbreak type shows slope={worst_jb[1]:+.6f} "
               f"(compliance rate vs BPW). Lower BPW = higher jailbreak success.")
        else:
            _w(lines, "**Finding 4 — Jailbreak Amplification:** Insufficient data.")
    else:
        _w(lines, "**Finding 4 — Jailbreak Amplification:** No jailbreak data available.")
    _w(lines)

    # Finding 5 — Per-category bias
    most_vulnerable = per_cat.get("most_vulnerable")
    least_vulnerable = per_cat.get("least_vulnerable")
    if most_vulnerable:
        _w(lines, f"**Finding 5 — Category Bias:** Most vulnerable category: **{most_vulnerable}**. "
           f"Least vulnerable: **{least_vulnerable}**.")
    else:
        _w(lines, "**Finding 5 — Category Bias:** Insufficient per-category data.")
    _w(lines)

    # Finding 6 — Judge agreement
    if judge.get("available"):
        per_task = judge.get("per_task", {})
        kappas = [v["kappa"] for v in per_task.values()]
        avg_kappa = sum(kappas) / len(kappas) if kappas else 0
        _w(lines, f"**Finding 6 — Judge Agreement:** Average Cohen's kappa = {avg_kappa:.3f} "
           f"across {len(per_task)} tasks.")
    else:
        _w(lines, f"**Finding 6 — Judge Agreement:** {judge.get('reason', 'Not available')}.")
    _w(lines)

    # Finding 7 — Critical thresholds
    if thresholds:
        parts = []
        for model, tdata in sorted(thresholds.items()):
            parts.append(f"{model}: {tdata.get('critical_quant', '?')} ({tdata.get('bpw', '?')} bpw)")
        _w(lines, "**Finding 7 — Critical Thresholds:** " + "; ".join(parts) + ".")
    _w(lines)

    # Finding 8 — Power
    mde_safety = power.get("mde_safety_pp")
    if mde_safety:
        _w(lines, f"**Finding 8 — Statistical Resolution:** MDE = {mde_safety}pp safety, "
           f"N={power.get('avg_safety_n_per_variant', '?')}/variant.")
    _w(lines)

    # Summary table
    if comparisons:
        _w(lines, "### Model-level Summary")
        _w(lines)
        _w(lines, "| Model | Safety Slope | Cap Slope | Divergence | CI Overlap | Verdict |")
        _w(lines, "|-------|-------------|-----------|------------|------------|---------|")
        for model, c in sorted(comparisons.items()):
            verdict = "**DEGRADES FASTER**" if c.get("safety_degrades_faster") else "Robust"
            _w(lines, f"| {model} | {c['avg_safety_slope']:+.4f} | "
               f"{c['avg_capability_slope']:+.4f} | {c['divergence']:+.4f} | "
               f"{'Yes' if c.get('ci_overlap') else 'No'} | {verdict} |")
        _w(lines)

    _w(lines, "---")
    _w(lines)


def _section_degradation_curves(
    lines: list[str], group_stats: dict[str, Any],
    domain: str, section_num: int, section_title: str,
) -> None:
    _w(lines, f"## {section_num}. {section_title}")
    _w(lines)
    _w(lines, "Scores normalized to highest-precision baseline (FP16 for small models, Q8_0 for 7B).")
    _w(lines)

    domain_entries = [d for d in group_stats.values() if d.get("domain") == domain]
    if not domain_entries:
        _w(lines, f"> No {domain} data available.")
        _w(lines)
        _w(lines, "---")
        _w(lines)
        return

    models = sorted(set(d["base_model"] for d in domain_entries))

    for model in models:
        _w(lines, f"### {model}")
        _w(lines)
        model_entries = [d for d in domain_entries if d["base_model"] == model]
        tasks = sorted(set(d["task"] for d in model_entries))

        for task in tasks:
            task_entries = sorted(
                [d for d in model_entries if d["task"] == task],
                key=lambda x: _sort_quant(x["quant"]),
            )
            if not task_entries:
                continue

            metric = task_entries[0].get("metric", "---")
            _w(lines, f"**Task:** `{task}` | **Metric:** `{metric}`")
            _w(lines)
            _w(lines, "| Quant | BPW | N | Score | CI | vs Baseline (pp) | Normalized |")
            _w(lines, "|-------|-----|---|-------|----|-------------------|------------|")

            for entry in task_entries:
                ci_str = _fmt_ci(entry.get("ci_lower"), entry.get("ci_upper"))
                delta = entry.get("delta_pp")
                delta_str = f"{delta:+.1f}" if delta is not None else "---"
                norm = entry.get("normalized_score", 1.0)
                norm_str = f"{norm:.3f}"
                if norm < 0.90:
                    norm_str = f"**{norm_str}**"
                _w(lines, f"| {entry['quant']} | {entry.get('bpw', '?')} | {entry['n']} | "
                   f"{entry['mean_score']:.3f} | {ci_str} | {delta_str} | {norm_str} |")
            _w(lines)

    _w(lines, "---")
    _w(lines)


def _section_slope_analysis(lines: list[str], slopes: dict, slope_cis: dict) -> None:
    _w(lines, "## 4. Slope Analysis")
    _w(lines)
    _w(lines, "Linear regression of normalized score vs BPW. Positive slope = better with more precision.")
    _w(lines)

    if not slopes:
        _w(lines, "> No slope data available.")
        _w(lines, "---")
        _w(lines)
        return

    _w(lines, "| Model | Domain | Metric | Slope | R² | CI Lower | CI Upper | N |")
    _w(lines, "|-------|--------|--------|-------|----|----------|----------|---|")

    for key, data in sorted(slopes.items(), key=lambda kv: (kv[1]["base_model"], kv[1]["domain"])):
        ci = slope_cis.get(key, {})
        ci_lo = f"{ci['ci_lower']:+.4f}" if "ci_lower" in ci else "---"
        ci_hi = f"{ci['ci_upper']:+.4f}" if "ci_upper" in ci else "---"
        _w(lines, f"| {data['base_model']} | {data['domain']} | {data['metric']} | "
           f"{data['slope']:+.4f} | {data['r_squared']:.3f} | {ci_lo} | {ci_hi} | {data['n_points']} |")
    _w(lines)
    _w(lines, "---")
    _w(lines)


def _section_safety_vs_capability(lines: list[str], comparisons: dict) -> None:
    _w(lines, "## 5. Safety vs Capability Comparison")
    _w(lines)

    if not comparisons:
        _w(lines, "> No comparison data available.")
        _w(lines, "---")
        _w(lines)
        return

    _w(lines, "| Model | Safety Slope | Cap Slope | Divergence | CI Overlap | Conclusion |")
    _w(lines, "|-------|-------------|-----------|------------|------------|------------|")
    for model, c in sorted(comparisons.items()):
        conclusion_short = c.get("conclusion", "---").split(":")[0]
        _w(lines, f"| {model} | {c['avg_safety_slope']:+.4f} | "
           f"{c['avg_capability_slope']:+.4f} | {c['divergence']:+.4f} | "
           f"{'Yes' if c.get('ci_overlap') else 'No'} | {conclusion_short} |")
    _w(lines)
    _w(lines, "---")
    _w(lines)


def _section_per_benchmark(lines: list[str], group_stats: dict) -> None:
    _w(lines, "## 6. Per-Benchmark Breakdown")
    _w(lines)

    tasks = sorted(set(d["task"] for d in group_stats.values()))
    if not tasks:
        _w(lines, "> No benchmark data.")
        _w(lines, "---")
        _w(lines)
        return

    for task in tasks:
        domain_vals = set(d["domain"] for d in group_stats.values() if d["task"] == task)
        domain_label = next(iter(domain_vals), "unknown")
        _w(lines, f"### {task} ({domain_label})")
        _w(lines)
        _w(lines, "| Model | Quant | BPW | N | Score | Normalized | vs Baseline |")
        _w(lines, "|-------|-------|-----|---|-------|------------|-------------|")

        entries = sorted(
            [d for d in group_stats.values() if d["task"] == task],
            key=lambda x: (x["base_model"], _sort_quant(x["quant"])),
        )
        for e in entries:
            delta = e.get("delta_pp")
            delta_str = f"{delta:+.1f}" if delta is not None else "---"
            _w(lines, f"| {e['base_model']} | {e['quant']} | {e.get('bpw', '?')} | "
               f"{e['n']} | {e['mean_score']:.3f} | {e.get('normalized_score', 1.0):.3f} | "
               f"{delta_str} |")
        _w(lines)

    _w(lines, "---")
    _w(lines)


def _section_critical_thresholds(lines: list[str], thresholds: dict) -> None:
    _w(lines, "## 7. Critical Thresholds")
    _w(lines)
    _w(lines, "Last quant level where safety/capability ratio >= 0.95.")
    _w(lines)

    if not thresholds:
        _w(lines, "> No threshold data.")
        _w(lines, "---")
        _w(lines)
        return

    _w(lines, "| Model | Baseline | Critical Quant | BPW | Last Safe Ratio |")
    _w(lines, "|-------|----------|---------------|-----|----------------|")
    for model, data in sorted(thresholds.items()):
        _w(lines, f"| {model} | {data.get('baseline_quant', 'FP16')} | "
           f"{data.get('critical_quant', '---')} | {data.get('bpw', '?')} | "
           f"{data.get('last_safe_ratio', 0):.4f} |")
    _w(lines)
    _w(lines, "---")
    _w(lines)


def _section_pairwise_tests(lines: list[str], pairwise: list) -> None:
    _w(lines, "## 8. Statistical Tests (Pairwise)")
    _w(lines)

    if not pairwise:
        _w(lines, "> No pairwise test data.")
        _w(lines, "---")
        _w(lines)
        return

    for domain in ("safety", "capability"):
        domain_tests = [t for t in pairwise if t.get("domain") == domain]
        sig_tests = [t for t in domain_tests if t.get("significant")]
        _w(lines, f"### {domain.title()} ({len(sig_tests)}/{len(domain_tests)} significant)")
        _w(lines)

        if sig_tests:
            _w(lines, "| Model | Task | Higher Q | Lower Q | Cohen's d | p-value |")
            _w(lines, "|-------|------|----------|---------|-----------|---------|")
            for t in sorted(sig_tests, key=lambda x: (x["base_model"], x["task"])):
                _w(lines, f"| {t['base_model']} | {t['task']} | {t['quant_higher']} | "
                   f"{t['quant_lower']} | {t['effect_size_d']:.3f} | {t['p_value']:.4f} |")
            _w(lines)
        else:
            _w(lines, f"*No significant {domain} differences at p < 0.05.*")
            _w(lines)

    _w(lines, "---")
    _w(lines)


def _section_power_analysis(lines: list[str], power: dict) -> None:
    _w(lines, "## 9. Power Analysis")
    _w(lines)

    if not power:
        _w(lines, "> Power analysis not available.")
        _w(lines, "---")
        _w(lines)
        return

    _w(lines, "| Metric Type | N per Variant | MDE |")
    _w(lines, "|------------|--------------|-----|")
    if power.get("mde_safety_pp") is not None:
        _w(lines, f"| Safety (binary) | {power['avg_safety_n_per_variant']} | {power['mde_safety_pp']}pp |")
    if power.get("mde_capability_pp") is not None:
        _w(lines, f"| Capability (binary) | {power['avg_capability_n_per_variant']} | {power['mde_capability_pp']}pp |")
    _w(lines)
    _w(lines, f"**Interpretation:** {power.get('interpretation', 'N/A')}")
    _w(lines)
    _w(lines, "---")
    _w(lines)


def _section_cross_phase(lines: list[str], cross_phase: list) -> None:
    _w(lines, "## 10. Cross-Phase Validation")
    _w(lines)

    if not cross_phase:
        _w(lines, "> Phase 2 results not found — cross-phase validation skipped.")
        _w(lines, "---")
        _w(lines)
        return

    _w(lines, "| Model | Quant | Task | Phase 2 Mean | Phase 3 Mean | Diff % | Status |")
    _w(lines, "|-------|-------|------|-------------|-------------|--------|--------|")
    for c in sorted(cross_phase, key=lambda x: (x["base_model"], x["task"])):
        status = "OK" if c.get("consistent") else "**DIVERGENT**"
        _w(lines, f"| {c['base_model']} | {c['quant']} | {c['task']} | "
           f"{c['phase2_mean']:.4f} | {c['phase3_mean']:.4f} | "
           f"{c['diff_pct']:+.1f}% | {status} |")
    _w(lines)

    consistent = sum(1 for c in cross_phase if c.get("consistent"))
    _w(lines, f"**{consistent}/{len(cross_phase)} consistent** (< 5% difference).")
    _w(lines)
    _w(lines, "---")
    _w(lines)


def _section_ratio_table(lines: list[str], thresholds: dict) -> None:
    _w(lines, "## 11. Per-Quant Safety/Capability Ratio")
    _w(lines)

    if not thresholds:
        _w(lines, "> No threshold data.")
        _w(lines, "---")
        _w(lines)
        return

    for model, data in sorted(thresholds.items()):
        per_quant = data.get("per_quant", [])
        if not per_quant:
            continue
        _w(lines, f"### {model}")
        _w(lines)
        _w(lines, "| Quant | BPW | Safety Norm | Cap Norm | Ratio |")
        _w(lines, "|-------|-----|------------|----------|-------|")
        for pq in per_quant:
            ratio = pq.get("ratio", 1.0)
            ratio_str = f"**{ratio:.4f}**" if ratio < 0.95 else f"{ratio:.4f}"
            _w(lines, f"| {pq['quant']} | {pq.get('bpw', '?')} | "
               f"{pq.get('safety_normalized', 0):.4f} | "
               f"{pq.get('capability_normalized', 0):.4f} | {ratio_str} |")
        _w(lines)

    _w(lines, "---")
    _w(lines)


def _section_methodology_base(lines: list[str]) -> None:
    _w(lines, "## 12. Methodology (Base)")
    _w(lines)
    _w(lines, "### Models")
    _w(lines)
    _w(lines, "| Model | Family | Params | Quant Levels | Baseline |")
    _w(lines, "|-------|--------|--------|-------------|----------|")
    _w(lines, "| Llama 3.2 1B | Llama | 1.2B | 7 (FP16-Q2_K) | FP16 |")
    _w(lines, "| Llama 3.2 3B | Llama | 3.2B | 7 (FP16-Q2_K) | FP16 |")
    _w(lines, "| Mistral 7B Instruct v0.3 | Mistral | 7.2B | 6 (Q8_0-Q2_K) | Q8_0 |")
    _w(lines, "| Qwen 2.5 7B Instruct | Qwen | 7.6B | 6 (Q8_0-Q2_K) | Q8_0 |")
    _w(lines)
    _w(lines, "7B models use Q8_0 as baseline (FP16 too large at ~14.5GB for single GPU).")
    _w(lines)
    _w(lines, "---")
    _w(lines)


# ── NEW Sections (13-18) ────────────────────────────────────────────────────


def _section_per_category_bias(lines: list[str], per_cat: dict) -> None:
    _w(lines, "## 13. Per-Category Bias Analysis")
    _w(lines)

    category_slopes = per_cat.get("category_slopes", {})
    if not category_slopes:
        _w(lines, "> No per-category bias data available.")
        _w(lines, "---")
        _w(lines)
        return

    _w(lines, "BBQ bias scores grouped by demographic category. More negative slope = "
       "more vulnerable to quantization-induced bias amplification.")
    _w(lines)

    ranked = per_cat.get("ranked_categories", [])
    _w(lines, "### Category Vulnerability Ranking (most to least vulnerable)")
    _w(lines)
    _w(lines, "| Rank | Category | Avg Slope | N Models |")
    _w(lines, "|------|----------|-----------|----------|")
    for i, cat in enumerate(ranked, 1):
        cs = category_slopes.get(cat, {})
        _w(lines, f"| {i} | {cat} | {cs.get('avg_slope', 0):+.6f} | {cs.get('n_models', 0)} |")
    _w(lines)

    most = per_cat.get("most_vulnerable")
    least = per_cat.get("least_vulnerable")
    if most and least:
        _w(lines, f"**Key finding:** *{most}* bias is amplified most by quantization, "
           f"while *{least}* bias is most robust.")
    _w(lines)
    _w(lines, "---")
    _w(lines)


def _section_jailbreak(lines: list[str], jailbreak: dict) -> None:
    _w(lines, "## 14. Jailbreak Amplification Results")
    _w(lines)

    if not jailbreak.get("available"):
        _w(lines, "> No jailbreak data available.")
        _w(lines, "---")
        _w(lines)
        return

    _w(lines, f"Total jailbreak samples: {jailbreak.get('n_total', 0)}")
    _w(lines)

    # Success rates by type
    success_rates = jailbreak.get("success_rates", {})
    if success_rates:
        _w(lines, "### Compliance Rate by Jailbreak Type")
        _w(lines)
        _w(lines, "| Jailbreak Type | Model | Quant | N | Compliance Rate | Refusal Rate |")
        _w(lines, "|---------------|-------|-------|---|-----------------|--------------|")
        for jb_type in sorted(success_rates.keys()):
            for entry in sorted(success_rates[jb_type],
                                key=lambda e: (e["base_model"], _sort_quant(e["quant"]))):
                _w(lines, f"| {jb_type} | {entry['base_model']} | {entry['quant']} | "
                   f"{entry['n']} | {entry['compliance_rate']:.3f} | {entry['refusal_rate']:.3f} |")
        _w(lines)

    # Amplification ratios
    amplification = jailbreak.get("amplification", {})
    if amplification:
        _w(lines, "### Amplification Ratios (jailbreak compliance / direct compliance)")
        _w(lines)
        _w(lines, "| Jailbreak Type | Model | Quant | Direct Compliance | JB Compliance | Amplification |")
        _w(lines, "|---------------|-------|-------|-------------------|---------------|---------------|")
        for jb_type in sorted(amplification.keys()):
            for entry in sorted(amplification[jb_type],
                                key=lambda e: (e["base_model"], _sort_quant(e["quant"]))):
                amp = entry.get("amplification_ratio")
                amp_str = f"{amp:.2f}x" if amp is not None else "N/A"
                _w(lines, f"| {jb_type} | {entry['base_model']} | {entry['quant']} | "
                   f"{entry['direct_compliance']:.3f} | {entry['jailbreak_compliance']:.3f} | "
                   f"{amp_str} |")
        _w(lines)

    # BPW slopes
    jb_slopes = jailbreak.get("jailbreak_slopes", {})
    if jb_slopes:
        _w(lines, "### Compliance Rate vs BPW Slopes")
        _w(lines)
        _w(lines, "Negative slope = compliance increases as BPW decreases (more jailbreak-susceptible).")
        _w(lines)
        _w(lines, "| Jailbreak Type | Slope |")
        _w(lines, "|---------------|-------|")
        for jb_type, slope in sorted(jb_slopes.items()):
            _w(lines, f"| {jb_type} | {slope:+.6f} |")
        _w(lines)

    _w(lines, "---")
    _w(lines)


def _section_judge_agreement(lines: list[str], judge: dict) -> None:
    _w(lines, "## 15. LLM Judge Agreement")
    _w(lines)

    if not judge.get("available"):
        _w(lines, f"> {judge.get('reason', 'Judge data not available')}.")
        _w(lines, "---")
        _w(lines)
        return

    _w(lines, f"Judge model: **{judge.get('judge_model', 'qwen2.5:7b-instruct-q8_0')}**")
    _w(lines, f"Total judged samples: {judge.get('n_judged', 0)}")
    _w(lines)

    # Per-task kappa
    per_task = judge.get("per_task", {})
    if per_task:
        _w(lines, "### Per-Task Cohen's Kappa")
        _w(lines)
        _w(lines, "| Task | Kappa | N Pairs | Agreement % |")
        _w(lines, "|------|-------|---------|-------------|")
        for task, data in sorted(per_task.items()):
            _w(lines, f"| {task} | {data['kappa']:.4f} | {data['n_pairs']} | "
               f"{data['agreement_pct']:.1f}% |")
        _w(lines)

    # Per-quant kappa
    per_quant = judge.get("per_task_per_quant", {})
    if per_quant:
        _w(lines, "### Kappa by Quantization Level")
        _w(lines)
        _w(lines, "Key question: does kappa decrease at lower quant? (Harder to classify = "
           "more divergent responses)")
        _w(lines)
        for task, quant_data in sorted(per_quant.items()):
            _w(lines, f"**{task}:**")
            _w(lines)
            _w(lines, "| Quant | Kappa | N Pairs | Agreement % |")
            _w(lines, "|-------|-------|---------|-------------|")
            for quant in QUANT_PRECISION_ORDER:
                if quant in quant_data:
                    d = quant_data[quant]
                    _w(lines, f"| {quant} | {d['kappa']:.4f} | {d['n_pairs']} | "
                       f"{d['agreement_pct']:.1f}% |")
            _w(lines)

    _w(lines, "---")
    _w(lines)


def _section_cross_family(lines: list[str], family_cmp: dict) -> None:
    _w(lines, "## 16. Cross-Family Comparison")
    _w(lines)

    if not family_cmp.get("available"):
        _w(lines, f"> {family_cmp.get('reason', 'Cross-family comparison not available')}.")
        _w(lines, "---")
        _w(lines)
        return

    _w(lines, "One-way ANOVA of safety degradation slopes across model families.")
    _w(lines)
    _w(lines, f"**F-statistic:** {family_cmp['f_statistic']:.4f}")
    p_val = family_cmp.get("p_value")
    _w(lines, f"**p-value:** {p_val:.6f}" if p_val is not None else "**p-value:** N/A")
    _w(lines, f"**df:** ({family_cmp['df_between']}, {family_cmp['df_within']})")
    _w(lines, f"**Conclusion:** {family_cmp['conclusion']}")
    _w(lines)

    per_family = family_cmp.get("per_family", {})
    if per_family:
        _w(lines, "### Per-Family Safety Slopes")
        _w(lines)
        _w(lines, "| Family | N Slopes | Mean Slope |")
        _w(lines, "|--------|----------|------------|")
        for family, data in sorted(per_family.items()):
            _w(lines, f"| {family} | {data['n_slopes']} | {data['mean_slope']:+.6f} |")
        _w(lines)

    _w(lines, "---")
    _w(lines)


def _section_multi_family_slopes(lines: list[str], slopes: dict, comparisons: dict) -> None:
    _w(lines, "## 17. Multi-Family Slope Comparison")
    _w(lines)
    _w(lines, "Is safety degradation universal or family-specific?")
    _w(lines)

    if not slopes:
        _w(lines, "> No slope data.")
        _w(lines, "---")
        _w(lines)
        return

    # Group slopes by domain
    safety_slopes_by_model = {}
    cap_slopes_by_model = {}
    for key, data in slopes.items():
        if data["domain"] == "safety":
            safety_slopes_by_model.setdefault(data["base_model"], []).append(data["slope"])
        elif data["domain"] == "capability":
            cap_slopes_by_model.setdefault(data["base_model"], []).append(data["slope"])

    _w(lines, "| Model | Avg Safety Slope | Avg Cap Slope | Safety More Sensitive? |")
    _w(lines, "|-------|-----------------|---------------|----------------------|")
    for model in sorted(set(list(safety_slopes_by_model) + list(cap_slopes_by_model))):
        s_slopes = safety_slopes_by_model.get(model, [])
        c_slopes = cap_slopes_by_model.get(model, [])
        avg_s = sum(s_slopes) / len(s_slopes) if s_slopes else 0
        avg_c = sum(c_slopes) / len(c_slopes) if c_slopes else 0
        more_sensitive = "Yes" if avg_s > avg_c else "No"
        _w(lines, f"| {model} | {avg_s:+.6f} | {avg_c:+.6f} | {more_sensitive} |")
    _w(lines)

    _w(lines, "---")
    _w(lines)


def _section_methodology_extended(lines: list[str]) -> None:
    _w(lines, "## 18. Updated Methodology & Limitations")
    _w(lines)
    _w(lines, "### Phase 3 Additions")
    _w(lines)
    _w(lines, "- **Multi-family evaluation**: 4 model families (3 RLHF recipes, 2 size classes)")
    _w(lines, "- **LLM-as-judge**: Qwen 2.5 7B Instruct (Q8_0) validates regex classifiers post-hoc")
    _w(lines, "- **Jailbreak amplification**: 120 prompts (30 direct + 90 jailbroken across 3 techniques)")
    _w(lines, "- **Per-category BBQ**: 200 samples (4x Phase 2) for per-demographic-category analysis")
    _w(lines, "- **Cross-family ANOVA**: Tests whether safety slopes differ significantly across families")
    _w(lines)
    _w(lines, "### Normalization")
    _w(lines)
    _w(lines, "- Small models (1B-3B): normalized to FP16 = 1.000")
    _w(lines, "- 7B models: normalized to Q8_0 = 1.000 (FP16 too large for single GPU)")
    _w(lines)
    _w(lines, "### Limitations")
    _w(lines)
    _w(lines, "- **LLM judge may share biases**: The judge model (Qwen 2.5) may have "
       "correlated failure modes, especially for bias detection")
    _w(lines, "- **Jailbreak templates are representative, not exhaustive**: 3 techniques "
       "from ~4 major clusters; novel jailbreaks may behave differently")
    _w(lines, "- **7B models use Q8_0 baseline**: Direct comparison with small-model FP16 "
       "baselines should account for this normalization difference")
    _w(lines, "- **Single GPU (RTX 4080)**: 7B FP16 does not fit; results are hardware-specific")
    _w(lines, "- **Deterministic generation** (temp=0): No sampling variance measured")
    _w(lines, "- **BBQ category sample sizes**: With 200 total BBQ samples across ~9 categories, "
       "some categories may have < 25 samples per model-quant combination")


# ── Report Assembly ──────────────────────────────────────────────────────────


def generate_report(run_dir: Path) -> str:
    """Generate Phase 3 18-section markdown report."""
    analysis_path = run_dir / "phase3_analysis.json"
    if not analysis_path.exists():
        logger.error("No phase3_analysis.json found in %s", run_dir)
        return ""

    with open(analysis_path, encoding="utf-8") as f:
        analysis = json.load(f)

    group_stats = analysis.get("group_stats", {})
    slopes = analysis.get("degradation_slopes", {})
    slope_cis = analysis.get("slope_cis", {})
    comparisons = analysis.get("slope_comparisons", {})
    thresholds = analysis.get("critical_thresholds", {})
    pairwise = analysis.get("pairwise_tests", [])
    power = analysis.get("power_analysis", {})
    cross_phase = analysis.get("cross_phase_validation", [])
    per_cat = analysis.get("per_category_bias", {})
    jailbreak = analysis.get("jailbreak_amplification", {})
    judge = analysis.get("judge_agreement", {})
    family_cmp = analysis.get("family_comparison", {})

    lines: list[str] = []

    # Header
    _section_header(lines, analysis, run_dir)

    # 1. Executive Summary
    _section_executive_summary(lines, analysis)

    # 2-3. Degradation Curves
    _section_degradation_curves(lines, group_stats, "safety", 2, "Degradation Curves (Safety)")
    _section_degradation_curves(lines, group_stats, "capability", 3, "Degradation Curves (Capability)")

    # 4. Slope Analysis
    _section_slope_analysis(lines, slopes, slope_cis)

    # 5. Safety vs Capability
    _section_safety_vs_capability(lines, comparisons)

    # 6. Per-Benchmark
    _section_per_benchmark(lines, group_stats)

    # 7. Critical Thresholds
    _section_critical_thresholds(lines, thresholds)

    # 8. Pairwise Tests
    _section_pairwise_tests(lines, pairwise)

    # 9. Power Analysis
    _section_power_analysis(lines, power)

    # 10. Cross-Phase Validation
    _section_cross_phase(lines, cross_phase)

    # 11. Per-Quant Ratio
    _section_ratio_table(lines, thresholds)

    # 12. Base Methodology
    _section_methodology_base(lines)

    # 13-18: NEW sections
    _section_per_category_bias(lines, per_cat)
    _section_jailbreak(lines, jailbreak)
    _section_judge_agreement(lines, judge)
    _section_cross_family(lines, family_cmp)
    _section_multi_family_slopes(lines, slopes, comparisons)
    _section_methodology_extended(lines)

    report_text = "\n".join(lines)

    report_path = run_dir / "phase3_report.md"
    report_path.write_text(report_text, encoding="utf-8")
    logger.info("Wrote Phase 3 report: %s (%d lines)", report_path, len(lines))

    return report_text


def main() -> int:
    parser = argparse.ArgumentParser(description="TR134 Phase 3 report generation")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--run-dir", type=str, default=None)
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if args.run_dir:
        run_dir = Path(args.run_dir)
    else:
        run_dir = find_latest_run("research/tr134/results/phase3")

    if not run_dir or not run_dir.exists():
        logger.error("No run directory found. Run analysis first.")
        return 1

    report = generate_report(run_dir)
    if report:
        print(f"\nReport written to: {run_dir / 'phase3_report.md'}")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
