"""TR137: Generate unified safety tax report — 21 sections.

Sections:
  1. Header (with timestamp, sources, research questions)
  2. Executive Summary (headline numbers, model verdicts)
  3. Data Sources (with validation warnings)
  4. Cross-TR Baseline Validation (with per-task deltas)
  5. Effect Size Ranking (with bootstrap CI)
  6. Safety-Capability Asymmetry (per axis, with summary)
  7. Per-Task Vulnerability Matrix (with most-vulnerable flags)
  8. Quant x Concurrency Projection (additive model)
  9. Backend x Quant Decomposition
  10. Jailbreak Synthesis
  11. Family-Level Patterns (with ANOVA)
  12. Model-Axis Heterogeneity (I-squared)
  13. Safety-Adjusted Deployment Matrix (with risk coloring)
  14. Worst-Case Analysis (per axis + combined)
  15. Power and Sensitivity (with program-level MDE)
  16. Per-Category Bias Synthesis
  17. Judge Agreement Synthesis
  18. Cross-Axis Correlation
  19. Effect Decomposition (% per axis)
  20. Model-Level Verdict Table
  21. Methodology & Limitations

Usage:
    python research/tr137/generate_report.py [-v] [--analysis PATH]
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
import sys
from typing import Any

_DIR = Path(__file__).resolve().parent
_REPO = _DIR.parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from research.tr125.shared.utils import find_latest_run

logger = logging.getLogger("tr137.generate_report")

_RESULTS_DIR = _REPO / "research" / "tr137" / "results"


def _w(lines: list[str], text: str = "") -> None:
    lines.append(text)


def _fmt_ci(ci_lo: float | None, ci_hi: float | None) -> str:
    if ci_lo is None or ci_hi is None:
        return "---"
    return f"[{ci_lo:.2f}, {ci_hi:.2f}]"


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------


def _section_header(lines: list[str], analysis: dict) -> None:
    _w(lines, "# TR137: The Safety Tax of Inference Optimization")
    _w(lines)
    meta = analysis.get("metadata", {})
    n = meta.get("n_sources", 0)
    total = meta.get("total_samples_across_trs", 0)
    avail = meta.get("sources_available", {})

    _w(lines, f"**Generated:** {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}")
    _w(lines, f"**Sources:** {n}/3 loaded | **Samples:** {total:,}")
    sources_str = ", ".join(
        f"{k.upper()} ({'loaded' if v else 'missing'})" for k, v in avail.items()
    )
    _w(lines, f"**Status:** {sources_str}")
    _w(lines)

    # Research questions
    _w(lines, "### Research Questions")
    _w(lines)
    _w(
        lines,
        "1. Which inference optimization axis causes the most safety degradation?",
    )
    _w(lines, "2. Does safety erode faster than capability under each optimization?")
    _w(lines, "3. Do models agree on which axis is most dangerous? (heterogeneity)")
    _w(lines, "4. What is the projected safety cost of combined optimizations?")
    _w(
        lines,
        "5. Are jailbreak susceptibility patterns consistent across optimization axes?",
    )
    _w(lines, "6. Which demographic categories are most vulnerable across axes?")
    _w(lines, "7. Do models vulnerable on one axis tend to be vulnerable on others?")
    _w(lines)


def _section_executive_summary(lines: list[str], analysis: dict) -> None:
    _w(lines, "## 2. Executive Summary")
    _w(lines)
    h = analysis.get("headlines", {})

    _w(lines, "| Finding | Value |")
    _w(lines, "|---------|-------|")
    _w(
        lines,
        f"| Most dangerous axis | **{h.get('most_dangerous_axis', 'N/A')}** "
        f"(mean {h.get('most_dangerous_delta_pp', 0):.1f}pp safety loss) |",
    )
    _w(
        lines,
        f"| Max combined safety cost | {h.get('max_total_cost_pp', 0):.1f}pp "
        f"(quant + concurrency, additive) |",
    )
    _w(
        lines,
        f"| Critical-risk configs | {h.get('n_critical_configs', 0)} "
        f"/ {h.get('n_total_configs', 0)} total |",
    )
    _w(lines, f"| High-risk or worse | {h.get('n_high_risk_configs', 0)} |")
    _w(
        lines,
        f"| Safety degrades faster | {h.get('safety_degrades_faster_count', 'N/A')} "
        f"models/axes |",
    )
    _w(lines, f"| Total samples | {h.get('total_samples', 0):,} |")
    _w(lines, f"| Sources loaded | {h.get('n_sources', 0)}/3 |")
    if h.get("cross_axis_correlation"):
        _w(lines, f"| Cross-axis correlation | {h['cross_axis_correlation']} |")
    _w(lines)

    # Validation warnings
    warnings = analysis.get("metadata", {}).get("validation_warnings", [])
    if warnings:
        _w(lines, f"**Validation warnings ({len(warnings)}):**")
        for w in warnings:
            _w(lines, f"- {w}")
        _w(lines)


def _section_environment(lines: list[str], analysis: dict) -> None:
    _w(lines, "## 2b. Synthesis Environment")
    _w(lines)
    env = analysis.get("metadata", {}).get("environment", {})
    if not env:
        _w(lines, "*Environment not captured.*")
        _w(lines)
        return

    _w(lines, "| Property | Value |")
    _w(lines, "|----------|-------|")
    for key in (
        "platform",
        "python_version",
        "machine",
        "numpy_version",
        "scipy_version",
        "pandas_version",
        "ollama_available",
        "ollama_version",
        "in_docker",
    ):
        val = env.get(key)
        if val is not None:
            label = key.replace("_", " ").title()
            display = str(val).split("\n")[0][:80]  # first line, truncated
            _w(lines, f"| {label} | {display} |")
    _w(lines)


def _section_data_sources(lines: list[str], analysis: dict) -> None:
    _w(lines, "## 3. Data Sources")
    _w(lines)
    avail = analysis.get("metadata", {}).get("sources_available", {})
    sm = analysis.get("metadata", {}).get("source_meta", {})

    _w(lines, "| Source | Experiment | Records | Models | Status |")
    _w(lines, "|--------|-----------|---------|--------|--------|")
    for tr, name, extra in [
        ("tr134", "Quant x Safety", lambda d: f"{d.get('n_quants', '?')} quants"),
        ("tr135", "Concurrency x Safety", lambda d: f"N={d.get('n_levels', '?')}"),
        ("tr136", "Backend x Safety", lambda d: f"{d.get('n_backends', '?')} backends"),
    ]:
        status = "loaded" if avail.get(tr) else "**missing**"
        d = sm.get(tr, {})
        n_records = d.get("total_records", 0)
        n_models = d.get("n_models", 0)
        extra_info = extra(d) if d else "---"
        _w(
            lines,
            f"| {tr.upper()} | {name} | {n_records:,} | "
            f"{n_models} ({extra_info}) | {status} |",
        )
    _w(lines)

    # Outlier summary
    outlier_sum = analysis.get("metadata", {}).get("outlier_summary", {})
    if outlier_sum:
        total_outliers = sum(v.get("n_outliers", 0) for v in outlier_sum.values())
        if total_outliers > 0:
            _w(
                lines,
                f"**Outlier detection:** {total_outliers} outlier group(s) "
                "flagged across sources (IQR method)",
            )
            for label, info in sorted(outlier_sum.items()):
                n = info.get("n_outliers", 0)
                if n > 0:
                    _w(
                        lines,
                        f"- {label.upper()}: {n} outlier(s) in "
                        f"{info.get('n_groups', 0)} groups",
                    )
            _w(lines)
        else:
            _w(lines, "**Outlier detection:** No outliers detected in source data.")
            _w(lines)


def _section_cross_validation(lines: list[str], analysis: dict) -> None:
    _w(lines, "## 4. Cross-TR Baseline Validation")
    _w(lines)
    _w(
        lines,
        "Shared models at Q4_K_M/N=1/Ollama anchor. "
        f"Delta should be <{5.0}pp if TRs are consistent.",
    )
    _w(lines)
    cv = analysis.get("cross_validation", {})
    if not cv:
        _w(lines, "*No shared model data available.*")
        _w(lines)
        return

    for model, data in sorted(cv.items()):
        consistent = data.get("all_consistent")
        status = "All consistent" if consistent else "**INCONSISTENT**"
        n_incon = data.get("n_inconsistent_tasks", 0)
        _w(
            lines,
            f"### {model} — {status}"
            + (f" ({n_incon} task(s) exceed tolerance)" if n_incon else ""),
        )
        _w(lines)
        _w(lines, "| Task | TR134 | TR135 | TR136 | Delta (pp) | OK? |")
        _w(lines, "|------|-------|-------|-------|-----------|-----|")
        for task, td in sorted(data.get("per_task", {}).items()):
            scores = td.get("scores", {})
            s134 = f"{scores['tr134']:.4f}" if "tr134" in scores else "---"
            s135 = f"{scores['tr135']:.4f}" if "tr135" in scores else "---"
            s136 = f"{scores['tr136']:.4f}" if "tr136" in scores else "---"
            delta = td.get("max_delta_pp")
            delta_s = f"{delta:.2f}" if delta is not None else "---"
            ok = td.get("consistent")
            ok_s = "yes" if ok else ("**NO**" if ok is False else "---")
            _w(lines, f"| {task} | {s134} | {s135} | {s136} | {delta_s} | {ok_s} |")
        mean_d = data.get("mean_delta_pp")
        if mean_d is not None:
            _w(lines, f"\nMean delta: {mean_d:.2f}pp")
        _w(lines)


def _section_effect_ranking(lines: list[str], analysis: dict) -> None:
    _w(lines, "## 5. Effect Size Ranking")
    _w(lines)
    _w(lines, "Which optimization axis causes the most safety degradation?")
    _w(lines)

    es = analysis.get("effect_sizes", {})
    cis = analysis.get("effect_cis", {})
    agg = es.get("_aggregate_ranking", [])

    if agg:
        _w(lines, "### Aggregate (across models)")
        _w(lines)
        _w(lines, "| Rank | Axis | Mean Delta (pp) | 95% CI | N Models |")
        _w(lines, "|------|------|----------------|--------|----------|")
        for i, r in enumerate(agg, 1):
            axis = r["axis"]
            ci = cis.get(axis, {})
            ci_s = _fmt_ci(ci.get("ci_lower"), ci.get("ci_upper"))
            _w(
                lines,
                f"| {i} | {axis} | {r['mean_delta_pp']:.2f} | {ci_s} | {r['n_models']} |",
            )
        _w(lines)

    _w(lines, "### Per model")
    _w(lines)
    _w(lines, "| Model | Quant (pp) | Concurrency (pp) | Backend (pp) | Worst Axis |")
    _w(lines, "|-------|-----------|-----------------|-------------|------------|")
    for model, data in sorted(es.items()):
        if not isinstance(data, dict) or "model" not in data:
            continue
        q = data.get("quant", {}).get("delta_pp")
        c = data.get("concurrency", {}).get("delta_pp")
        b = data.get("backend", {}).get("delta_pp")
        q_s = f"{q:.2f}" if q is not None else "---"
        c_s = f"{c:.2f}" if c is not None else "---"
        b_s = f"{b:.2f}" if b is not None else "---"
        ranking = data.get("ranking", [])
        worst = ranking[0]["axis"] if ranking else "---"
        _w(lines, f"| {model} | {q_s} | {c_s} | {b_s} | {worst} |")
    _w(lines)

    # Cohen's d where available
    has_cohens = any(
        isinstance(d, dict) and d.get("quant", {}).get("cohens_d") is not None
        for d in es.values()
    )
    if has_cohens:
        _w(lines, "### Effect Sizes (Cohen's d)")
        _w(lines)
        _w(lines, "| Model | Quant d | Interpretation |")
        _w(lines, "|-------|---------|---------------|")
        for model, data in sorted(es.items()):
            if not isinstance(data, dict) or "model" not in data:
                continue
            d = data.get("quant", {}).get("cohens_d")
            if d is not None:
                interp = (
                    "large" if abs(d) > 0.8 else "medium" if abs(d) > 0.5 else "small"
                )
                _w(lines, f"| {model} | {d:.4f} | {interp} |")
        _w(lines)


def _section_asymmetry(lines: list[str], analysis: dict) -> None:
    _w(lines, "## 6. Safety-Capability Asymmetry")
    _w(lines)
    _w(lines, "Does safety erode faster than capability under each optimization?")
    _w(lines)
    asym = analysis.get("asymmetry", {})
    if not asym:
        _w(lines, "*No asymmetry data available.*")
        _w(lines)
        return

    # Summary by axis
    axis_sum = asym.get("_axis_summary", {})
    if axis_sum:
        _w(lines, "### Summary by Axis")
        _w(lines)
        _w(lines, "| Axis | Models | Safety Faster | % |")
        _w(lines, "|------|--------|--------------|---|")
        for axis_name in ("quantization", "concurrency", "backend"):
            s = axis_sum.get(axis_name, {})
            if s.get("n_models", 0) > 0:
                _w(
                    lines,
                    f"| {axis_name} | {s['n_models']} | "
                    f"{s['n_safety_faster']} | {s['pct_safety_faster']:.0f}% |",
                )
        _w(lines)

    # Detail table
    _w(lines, "### Per-Model Detail")
    _w(lines)
    _w(lines, "| Axis | Model | Family | Safety Slope | Capability Slope | Faster? |")
    _w(lines, "|------|-------|--------|-------------|-----------------|---------|")
    for key in sorted(k for k in asym if not k.startswith("_")):
        d = asym[key]
        if not isinstance(d, dict) or "axis" not in d:
            continue
        axis = d.get("axis", "?")
        model = d.get("model", "?")
        family = d.get("family", "?")
        if "safety_slope" in d:
            ss = f"{d['safety_slope']:.6f}"
            cs = f"{d.get('capability_slope', 0):.6f}"
            faster = "**YES**" if d.get("safety_degrades_faster") else "no"
        elif "safety_range_pp" in d:
            ss = f"{d['safety_range_pp']:.2f}pp range"
            cs = f"{d['capability_range_pp']:.2f}pp range"
            faster = "**YES**" if d.get("safety_more_variable") else "no"
        else:
            continue
        _w(lines, f"| {axis} | {model} | {family} | {ss} | {cs} | {faster} |")
    _w(lines)


def _section_task_vuln(lines: list[str], analysis: dict) -> None:
    _w(lines, "## 7. Per-Task Vulnerability Matrix")
    _w(lines)
    _w(
        lines,
        "Mean absolute slope per task per optimization axis. "
        "Higher = more vulnerable to that optimization.",
    )
    _w(lines)
    tv = analysis.get("task_vulnerability", {})
    if not tv:
        _w(lines, "*No task vulnerability data available.*")
        _w(lines)
        return

    _w(lines, "| Task | Quant Slope | Conc. Slope | Backend p | Most Vulnerable |")
    _w(lines, "|------|-----------|------------|-----------|----------------|")
    for task in sorted(tv.keys()):
        d = tv[task]
        qs = d.get("quant_mean_abs_slope")
        cs = d.get("concurrency_mean_abs_slope")
        bp = d.get("backend_min_chi_p")
        qs_s = f"{qs:.6f}" if qs is not None else "---"
        cs_s = f"{cs:.6f}" if cs is not None else "---"
        bp_s = f"{bp:.4f}" if bp is not None else "---"
        if bp is not None and bp < 0.05:
            bp_s = f"**{bp_s}**"
        mv = d.get("most_vulnerable_axis", "---")
        _w(lines, f"| {task} | {qs_s} | {cs_s} | {bp_s} | {mv} |")
    _w(lines)


def _section_qc_interaction(lines: list[str], analysis: dict) -> None:
    _w(lines, "## 8. Quant x Concurrency Projection")
    _w(lines)
    _w(lines, "Additive model: total_cost = quant_cost + concurrency_cost.")
    _w(lines, "True interaction requires factorial design (not available).")
    _w(lines)
    qc = analysis.get("quant_concurrency_interaction", {})
    if not qc:
        _w(lines, "*Requires both TR134 and TR135 data.*")
        _w(lines)
        return

    _w(lines, "| Model | Quant Cost (pp) | Conc. Cost (pp) | Total (pp) | Quant % |")
    _w(lines, "|-------|----------------|----------------|-----------|---------|")
    for model, d in sorted(qc.items()):
        _w(
            lines,
            f"| {model} | {d['quant_marginal_pp']:.2f} | "
            f"{d['concurrency_marginal_pp']:.2f} | "
            f"{d['additive_projection_pp']:.2f} | "
            f"{d.get('quant_pct_of_total', 50):.0f}% |",
        )
    _w(lines)


def _section_bq_decomp(lines: list[str], analysis: dict) -> None:
    _w(lines, "## 9. Backend x Quant Decomposition")
    _w(lines)
    bq = analysis.get("backend_quant_decomposition", {})
    if not bq:
        _w(lines, "*Requires TR136 data.*")
        _w(lines)
        return

    for model, data in sorted(bq.items()):
        _w(lines, f"### {model}")
        _w(lines)
        if isinstance(data, dict):
            for key, val in sorted(data.items()):
                if isinstance(val, (int, float)):
                    _w(
                        lines,
                        (
                            f"- **{key}:** {val:.4f}"
                            if isinstance(val, float)
                            else f"- **{key}:** {val}"
                        ),
                    )
                elif isinstance(val, dict):
                    _w(lines, f"- **{key}:**")
                    for k2, v2 in sorted(val.items()):
                        _w(lines, f"  - {k2}: {v2}")
        _w(lines)


def _section_jailbreak(lines: list[str], analysis: dict) -> None:
    _w(lines, "## 10. Jailbreak Synthesis")
    _w(lines)
    js = analysis.get("jailbreak_synthesis", {})
    if not js:
        _w(lines, "*No jailbreak data available.*")
        _w(lines)
        return

    if "quant_axis" in js:
        _w(lines, "### Quantization Axis (TR134)")
        _w(lines)
        qa = js["quant_axis"]
        _w(lines, f"Total jailbreak samples: {qa.get('n_total', 'N/A')}")
        if qa.get("most_effective_type"):
            _w(lines, f"Most effective technique: **{qa['most_effective_type']}**")
        if qa.get("least_effective_type"):
            _w(lines, f"Least effective technique: {qa['least_effective_type']}")
        _w(lines)

        slopes = qa.get("slopes", {})
        if slopes:
            _w(lines, "| Jailbreak Type | Slope (per BPW) | Interpretation |")
            _w(lines, "|---------------|----------------|---------------|")
            for m, s in sorted(slopes.items()):
                slope_val = s.get("slope", 0) if isinstance(s, dict) else s
                interp = (
                    "gets easier at lower quant"
                    if slope_val < 0
                    else "stable across quant"
                )
                _w(lines, f"| {m} | {slope_val:.6f} | {interp} |")
            _w(lines)

    if "concurrency_axis" in js:
        _w(lines, "### Concurrency Axis (TR135)")
        _w(lines)
        pm = js["concurrency_axis"].get("per_model", {})
        if pm:
            for model, data in sorted(pm.items()):
                _w(lines, f"**{model}:** {json.dumps(data, default=str)[:200]}")
            _w(lines)


def _section_family(lines: list[str], analysis: dict) -> None:
    _w(lines, "## 11. Family-Level Patterns")
    _w(lines)
    fp = analysis.get("family_patterns", {})
    if not fp:
        _w(lines, "*No family data available.*")
        _w(lines)
        return

    if "quant_axis" in fp:
        qa = fp["quant_axis"]
        p_val = qa.get("p_value")
        sig = p_val is not None and p_val < 0.05
        sig_str = "significant (p<0.05)" if sig else "not significant"
        if p_val is not None:
            _w(
                lines,
                f"**Quant axis ANOVA:** F={qa.get('f_statistic', 0):.2f}, "
                f"p={p_val:.4f} ({sig_str})",
            )
        else:
            _w(lines, f"**Quant axis ANOVA:** F={qa.get('f_statistic', 0):.2f}")
        _w(lines)

        per_fam = qa.get("per_family", {})
        if per_fam:
            _w(lines, "| Family | N Slopes | Mean Slope |")
            _w(lines, "|--------|---------|-----------|")
            for fam, data in sorted(per_fam.items()):
                if isinstance(data, dict):
                    _w(
                        lines,
                        f"| {fam} | {data.get('n_slopes', 0)} | "
                        f"{data.get('mean_slope', 0):.6f} |",
                    )
            _w(lines)

    ca = fp.get("cross_axis", {})
    if ca:
        _w(lines, "**Cross-axis effects by family:**")
        _w(lines)
        for family, effects in sorted(ca.items()):
            if isinstance(effects, dict):
                effect_strs = [f"{k}: {v:+.1f}pp" for k, v in sorted(effects.items())]
                _w(lines, f"- **{family}:** {', '.join(effect_strs)}")
        _w(lines)


def _section_heterogeneity(lines: list[str], analysis: dict) -> None:
    _w(lines, "## 12. Model-Axis Heterogeneity (I-squared)")
    _w(lines)
    _w(
        lines,
        "Do models agree on which axis hurts safety most? "
        "I-sq >75% = high disagreement.",
    )
    _w(lines)
    het = analysis.get("heterogeneity", {})
    if not het:
        _w(lines, "*Requires multiple models per axis.*")
        _w(lines)
        return

    _w(lines, "| Axis | N | Mean (pp) | SD | Range | I-sq | Interp. |")
    _w(lines, "|------|---|----------|-----|-------|------|---------|")
    for axis in ("quant", "concurrency", "backend"):
        d = het.get(axis)
        if d:
            _w(
                lines,
                f"| {axis} | {d['n_models']} | {d['mean_effect_pp']:.2f} | "
                f"{d['std_effect_pp']:.2f} | {d['range_pp']:.2f} | "
                f"{d['i_squared']:.1f}% | {d['interpretation']} |",
            )
    _w(lines)


def _section_deployment(lines: list[str], analysis: dict) -> None:
    _w(lines, "## 13. Safety-Adjusted Deployment Matrix")
    _w(lines)
    _w(
        lines,
        "Projected safety retention under combined optimizations (additive model). "
        "Configs sorted by risk level.",
    )
    _w(lines)
    dm = analysis.get("deployment_matrix", [])
    if not dm:
        _w(lines, "*Requires TR134 + TR135 data.*")
        _w(lines)
        return

    _w(
        lines,
        "| Model | Quant | N | Quant Cost | Conc Cost | Total | Retention | Risk |",
    )
    _w(lines, "|-------|-------|---|-----------|----------|-------|-----------|------|")
    for row in dm:
        risk = row["risk_level"]
        risk_s = f"**{risk.upper()}**" if risk in ("critical", "high") else risk
        ret = row["retention_pct"]
        ret_s = f"**{ret:.1f}%**" if ret < 90 else f"{ret:.1f}%"
        _w(
            lines,
            f"| {row['model']} | {row['quant']} | {row['n_agents']} | "
            f"{row['quant_cost_pp']:.1f}pp | {row['concurrency_cost_pp']:.1f}pp | "
            f"{row.get('total_cost_pp', 0):.1f}pp | {ret_s} | {risk_s} |",
        )
    _w(lines)

    # Risk distribution
    wc = analysis.get("worst_cases", {})
    counts = wc.get("risk_level_counts", {})
    if counts:
        dist = ", ".join(f"{level}: {n}" for level, n in sorted(counts.items()))
        _w(lines, f"**Risk distribution:** {dist}")
        _w(lines)


def _section_worst_case(lines: list[str], analysis: dict) -> None:
    _w(lines, "## 14. Worst-Case Analysis")
    _w(lines)
    wc = analysis.get("worst_cases", {})
    if not wc:
        _w(lines, "*No worst-case data available.*")
        _w(lines)
        return

    _w(lines, "### Per-Axis Worst Cases")
    _w(lines)
    _w(lines, "| Axis | Model | Delta (pp) | Detail |")
    _w(lines, "|------|-------|-----------|--------|")
    for axis in ("quant", "concurrency", "backend"):
        d = wc.get(axis)
        if d:
            detail = ""
            if axis == "quant":
                detail = (
                    f"{d.get('baseline_quant', '?')} -> {d.get('worst_quant', '?')}"
                )
            elif axis == "concurrency":
                detail = f"N=1 -> N={d.get('max_n', '?')}"
            elif axis == "backend":
                detail = (
                    f"{d.get('best_backend', '?')} -> {d.get('worst_backend', '?')}"
                )
            _w(
                lines,
                f"| {axis} | {d.get('model', '?')} | "
                f"**{d.get('delta_pp', 0):.2f}** | {detail} |",
            )
    _w(lines)

    cw = wc.get("combined_worst")
    if cw:
        _w(
            lines,
            f"**Worst combined config:** {cw.get('model', '?')} at "
            f"{cw.get('quant', '?')}/N={cw.get('n_agents', '?')} — "
            f"{cw.get('retention_pct', 0):.1f}% retention "
            f"(**{cw.get('risk_level', '?')}**)",
        )

    _w(lines, f"**Maximum total safety cost:** {wc.get('max_total_cost_pp', 0):.1f}pp")
    _w(lines)


def _section_power(lines: list[str], analysis: dict) -> None:
    _w(lines, "## 15. Power and Sensitivity")
    _w(lines)
    pa = analysis.get("power_analysis", {})
    if not pa:
        _w(lines, "*No power data available.*")
        _w(lines)
        return

    _w(lines, "| Source | MDE Safety (pp) | Avg N/Variant | Detail |")
    _w(lines, "|--------|----------------|--------------|--------|")
    for src in ("tr134", "tr135", "tr136"):
        d = pa.get(src, {})
        mde = d.get("mde_safety_pp") or d.get("mean_mde_safety_pp")
        mde_s = f"{mde:.1f}" if mde is not None else "---"
        avg_n = d.get("avg_n_per_variant")
        avg_n_s = str(avg_n) if avg_n is not None else "---"
        interp = d.get("interpretation", "")[:60]
        _w(lines, f"| {src.upper()} | {mde_s} | {avg_n_s} | {interp} |")

    sensitivity = pa.get("program_sensitivity", "")
    if sensitivity:
        _w(lines, f"\n**Program sensitivity:** {sensitivity}")

    best = pa.get("best_mde_pp")
    worst = pa.get("worst_mde_pp")
    if best is not None and worst is not None:
        _w(lines, f"Best MDE: {best:.1f}pp | Worst MDE: {worst:.1f}pp")
        _w(
            lines,
            f"Effects smaller than {worst:.1f}pp may be undetectable "
            "in at least one source TR.",
        )
    _w(lines)


def _section_bias_synthesis(lines: list[str], analysis: dict) -> None:
    _w(lines, "## 16. Per-Category Bias Synthesis")
    _w(lines)
    bs = analysis.get("bias_synthesis", {})
    if not bs.get("available"):
        _w(
            lines,
            "*No per-category bias data available. "
            "Requires TR134 per_category_bias results.*",
        )
        _w(lines)
        return

    qa = bs.get("quant_axis", {})
    if qa:
        _w(lines, "### Quantization Axis (TR134)")
        _w(lines)
        _w(lines, f"**Most vulnerable category:** {qa.get('most_vulnerable', 'N/A')}")
        _w(lines, f"**Least vulnerable category:** {qa.get('least_vulnerable', 'N/A')}")
        _w(lines)

        ranked = qa.get("ranked_categories", [])
        slopes = qa.get("category_slopes", {})
        if ranked and slopes:
            _w(lines, "| Rank | Category | Avg Slope | N Models |")
            _w(lines, "|------|----------|----------|----------|")
            for i, cat in enumerate(ranked, 1):
                cs = slopes.get(cat, {})
                avg = cs.get("avg_slope", 0)
                nm = cs.get("n_models", 0)
                _w(lines, f"| {i} | {cat} | {avg:.6f} | {nm} |")
            _w(lines)

    if bs.get("concurrency_axis_available"):
        _w(
            lines,
            f"Concurrency axis: {bs.get('concurrency_n_bias_groups', 0)} "
            "bias group(s) available for deeper analysis.",
        )
    if bs.get("backend_axis_available"):
        _w(
            lines,
            f"Backend axis: {bs.get('backend_n_bias_groups', 0)} "
            "bias group(s) available.",
        )
    _w(lines)


def _section_judge_synthesis(lines: list[str], analysis: dict) -> None:
    _w(lines, "## 17. Judge Agreement Synthesis")
    _w(lines)
    js = analysis.get("judge_synthesis", {})
    if not js.get("available"):
        _w(
            lines,
            "*No LLM judge data available. "
            "Run judge_analysis.py in source TRs first.*",
        )
        _w(lines)
        return

    for axis_key, axis_label in [
        ("quant_axis", "Quantization (TR134)"),
        ("concurrency_axis", "Concurrency (TR135)"),
        ("backend_axis", "Backend (TR136)"),
    ]:
        d = js.get(axis_key, {})
        if not d:
            continue
        _w(lines, f"### {axis_label}")
        _w(lines)
        _w(lines, f"Judged samples: {d.get('n_judged', 0):,}")
        kappa = d.get("overall_kappa")
        if kappa is not None:
            interp = (
                "excellent"
                if kappa > 0.8
                else (
                    "good"
                    if kappa > 0.6
                    else (
                        "moderate" if kappa > 0.4 else "fair" if kappa > 0.2 else "poor"
                    )
                )
            )
            _w(lines, f"Overall kappa: {kappa:.4f} ({interp})")
        _w(lines)
    _w(lines)


def _section_correlation(lines: list[str], analysis: dict) -> None:
    _w(lines, "## 18. Cross-Axis Correlation")
    _w(lines)
    _w(lines, "Are models vulnerable on one axis also vulnerable on others?")
    _w(lines)
    corr = analysis.get("correlation", {})
    if not corr.get("sufficient_data"):
        _w(
            lines,
            "*Requires >= 3 shared models per axis pair. "
            "Insufficient overlap in current data.*",
        )
        _w(lines)
        return

    _w(lines, "| Axis Pair | Pearson r | N Models | Interpretation |")
    _w(lines, "|-----------|----------|----------|---------------|")
    for pair_key in (
        "quant_vs_concurrency",
        "quant_vs_backend",
        "concurrency_vs_backend",
    ):
        d = corr.get(pair_key, {})
        if not isinstance(d, dict) or d.get("r") is None:
            continue
        label = pair_key.replace("_vs_", " vs ")
        r = d["r"]
        interp = d.get("interpretation", "")
        _w(lines, f"| {label} | {r:.4f} | {d['n_models']} | {interp} |")
    _w(lines)


def _section_decomposition(lines: list[str], analysis: dict) -> None:
    _w(lines, "## 19. Effect Decomposition")
    _w(lines)
    _w(lines, "What % of total safety cost comes from each optimization axis?")
    _w(lines)
    decomp = analysis.get("decomposition", {})
    if not decomp:
        _w(lines, "*No decomposition data available.*")
        _w(lines)
        return

    # Per-model table
    has_data = False
    for m, d in decomp.items():
        if m.startswith("_") or not isinstance(d, dict) or "per_axis" not in d:
            continue
        has_data = True

    if has_data:
        _w(
            lines,
            "| Model | Total (pp) | Quant % | Concurrency % | Backend % | Dominant |",
        )
        _w(
            lines,
            "|-------|-----------|---------|--------------|----------|----------|",
        )
        for m, d in sorted(decomp.items()):
            if m.startswith("_") or not isinstance(d, dict) or "per_axis" not in d:
                continue
            pa = d["per_axis"]
            q_pct = pa.get("quant", {}).get("pct_of_total", "---")
            c_pct = pa.get("concurrency", {}).get("pct_of_total", "---")
            b_pct = pa.get("backend", {}).get("pct_of_total", "---")
            q_s = f"{q_pct:.0f}%" if isinstance(q_pct, (int, float)) else q_pct
            c_s = f"{c_pct:.0f}%" if isinstance(c_pct, (int, float)) else c_pct
            b_s = f"{b_pct:.0f}%" if isinstance(b_pct, (int, float)) else b_pct
            _w(
                lines,
                f"| {m} | {d['total_pp']:.1f} | {q_s} | {c_s} | {b_s} | "
                f"**{d['dominant_axis']}** |",
            )
        _w(lines)

    # Aggregate
    agg = decomp.get("_aggregate", {})
    if agg:
        _w(lines, "**Aggregate breakdown:**")
        for axis, data in sorted(agg.items()):
            _w(
                lines,
                f"- {axis}: {data['mean_pct']:.0f}% of total (n={data['n_models']})",
            )
        _w(lines)


def _section_verdict(lines: list[str], analysis: dict) -> None:
    _w(lines, "## 20. Model-Level Verdicts")
    _w(lines)
    _w(lines, "Per-model safety assessment across all optimization axes.")
    _w(lines)
    es = analysis.get("effect_sizes", {})
    asym = analysis.get("asymmetry", {})
    decomp = analysis.get("decomposition", {})

    models = [m for m in es if isinstance(es[m], dict) and "model" in es[m]]
    if not models:
        _w(lines, "*No model data available for verdicts.*")
        _w(lines)
        return

    _w(lines, "| Model | Worst Axis | Max Delta (pp) | Safety > Cap? | Risk |")
    _w(lines, "|-------|-----------|---------------|--------------|------|")
    for model in sorted(models):
        me = es[model]
        ranking = me.get("ranking", [])
        worst_axis = ranking[0]["axis"] if ranking else "N/A"
        max_delta = ranking[0]["abs_delta_pp"] if ranking else 0

        # Check asymmetry across all axes
        safety_faster = False
        for key, d in asym.items():
            if isinstance(d, dict) and d.get("model", "").startswith(
                model.split("-")[0]
            ):
                if d.get("safety_degrades_faster"):
                    safety_faster = True
                    break

        risk = (
            "critical"
            if max_delta > 30
            else "high" if max_delta > 15 else "moderate" if max_delta > 5 else "low"
        )
        risk_s = f"**{risk.upper()}**" if risk in ("critical", "high") else risk

        _w(
            lines,
            f"| {model} | {worst_axis} | {max_delta:.1f} | "
            f"{'**YES**' if safety_faster else 'no'} | {risk_s} |",
        )
    _w(lines)


def _section_methodology(lines: list[str], analysis: dict) -> None:
    _w(lines, "## 21. Methodology & Limitations")
    _w(lines)
    _w(lines, "### Statistical Methods")
    _w(lines)
    _w(
        lines,
        "1. **Cross-validation:** Anchor-point comparison at Q4_K_M/N=1/Ollama "
        "across TRs (tolerance: 5pp)",
    )
    _w(
        lines,
        "2. **Effect sizes:** Absolute safety delta (pp) from baseline to worst "
        "per axis, with Cohen's d where applicable",
    )
    _w(
        lines,
        "3. **Bootstrap CI:** 2,000-iteration bootstrap on cross-model effect "
        "size means (95% CI)",
    )
    _w(
        lines,
        "4. **Heterogeneity:** I-squared statistic across models per axis "
        "(0-25% low, 25-75% moderate, >75% high)",
    )
    _w(
        lines,
        "5. **Asymmetry:** Safety vs capability slope comparison per axis, "
        "with CI overlap assessment",
    )
    _w(
        lines,
        "6. **Deployment projection:** Additive model (quant + concurrency "
        "marginal effects), risk-tiered at 95/90/80% retention",
    )
    _w(lines, "7. **Cross-axis correlation:** Pearson r across models per axis pair")
    _w(
        lines,
        "8. **Effect decomposition:** Percentage attribution of total safety "
        "cost per axis",
    )
    _w(lines)
    _w(lines, "### Limitations")
    _w(lines)
    _w(
        lines,
        "1. **No factorial design:** Cannot measure quant x concurrency "
        "interaction directly",
    )
    _w(
        lines,
        "2. **Additive assumption:** Deployment matrix assumes no synergistic "
        "effects between axes",
    )
    _w(
        lines,
        "3. **Shared model coverage:** Only Llama 3.2 1B/3B appear in all "
        "three TRs (2 anchor points)",
    )
    _w(
        lines,
        "4. **Qwen size mismatch:** Different Qwen sizes across TRs "
        "(7B/3B/1.5B) — not directly comparable",
    )
    _w(
        lines,
        "5. **Consumer hardware only:** Results may not generalize to "
        "datacenter GPUs or other accelerators",
    )
    _w(
        lines,
        "6. **Small model safety training:** 1B-3B models have weaker RLHF "
        "than frontier models",
    )
    _w(
        lines,
        "7. **Temperature 0:** Deterministic sampling; stochastic sampling "
        "may differ",
    )
    _w(
        lines,
        "8. **Automated scoring only:** Regex classifiers (no human annotation); "
        "LLM judge when available",
    )
    _w(
        lines,
        "9. **Meta-analysis limitations:** Synthesis operates on aggregated "
        "statistics, not raw samples — cannot recompute group statistics "
        "with different grouping",
    )
    _w(
        lines,
        "10. **Bootstrap on small N:** Cross-model bootstrap CIs are based on "
        "2-4 models per axis, limiting precision",
    )
    _w(lines)


# ---------------------------------------------------------------------------
# Report assembly
# ---------------------------------------------------------------------------


def generate_report(analysis: dict) -> str:
    """Generate full report as markdown string."""
    lines: list[str] = []

    _section_header(lines, analysis)
    _section_executive_summary(lines, analysis)
    _section_environment(lines, analysis)
    _section_data_sources(lines, analysis)
    _section_cross_validation(lines, analysis)
    _section_effect_ranking(lines, analysis)
    _section_asymmetry(lines, analysis)
    _section_task_vuln(lines, analysis)
    _section_qc_interaction(lines, analysis)
    _section_bq_decomp(lines, analysis)
    _section_jailbreak(lines, analysis)
    _section_family(lines, analysis)
    _section_heterogeneity(lines, analysis)
    _section_deployment(lines, analysis)
    _section_worst_case(lines, analysis)
    _section_power(lines, analysis)
    _section_bias_synthesis(lines, analysis)
    _section_judge_synthesis(lines, analysis)
    _section_correlation(lines, analysis)
    _section_decomposition(lines, analysis)
    _section_verdict(lines, analysis)
    _section_methodology(lines, analysis)

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="TR137 report generation")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument(
        "--analysis", type=Path, default=None, help="Path to tr137_analysis.json"
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    analysis_path = args.analysis
    if analysis_path is None:
        run_dir = find_latest_run(_RESULTS_DIR)
        if run_dir is None:
            logger.error("No TR137 results found in %s", _RESULTS_DIR)
            return 1
        analysis_path = run_dir / "tr137_analysis.json"

    if not analysis_path.exists():
        logger.error("Analysis file not found: %s", analysis_path)
        return 1

    with open(analysis_path, encoding="utf-8") as f:
        analysis = json.load(f)

    report = generate_report(analysis)

    report_path = analysis_path.parent / "tr137_report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    logger.info("Wrote report (%d lines) to %s", len(report.splitlines()), report_path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
