"""TR134 Phase 2: Generate comprehensive 12-section alignment robustness report.

Reads phase2_analysis.json and produces a full markdown report covering degradation
curves, slope analysis, safety vs capability comparison, statistical tests, power
analysis, cross-phase validation, and critical thresholds.

Report structure (12 sections):
  Header — data counts, task listing
  1.  Executive Summary — 6 numbered findings
  2.  Degradation Curves (Safety) — per-model tables with CI
  3.  Degradation Curves (Capability) — per-model tables with CI
  4.  Slope Analysis — full regression table
  5.  Safety vs Capability Comparison — per-model divergence
  6.  Per-Benchmark Breakdown — per-task model×quant tables
  7.  Critical Thresholds — per-quant safety/capability ratios
  8.  Statistical Tests (Pairwise) — significant results by domain
  9.  Power Analysis — MDE table and interpretation
  10. Cross-Phase Validation — Phase 1 vs Phase 2 consistency
  11. Per-Quant Safety/Capability Ratio — detailed ratio table
  12. Methodology & Limitations

Usage:
    python research/tr134/phase2/generate_report.py [-v] [--run-dir PATH]
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
from research.tr134.shared.utils import find_latest_run

logger = logging.getLogger("tr134.phase2.generate_report")


# ── Helpers ───────────────────────────────────────────────────────────────────


def _sort_quant(quant: str) -> int:
    """Sort key for quant levels — highest precision first (FP16=0)."""
    try:
        return QUANT_PRECISION_ORDER.index(quant)
    except ValueError:
        return len(QUANT_PRECISION_ORDER)


def _w(lines: list[str], text: str = "") -> None:
    lines.append(text)


def _detect_non_monotonic(group_stats: dict, domain: str) -> list[str]:
    """Detect models with non-monotonic degradation in given domain.

    Non-monotonic = score *increases* when moving from higher to lower precision
    by more than 0.01 normalized points (i.e., the lower-precision variant
    scores measurably better than its higher-precision neighbor).
    """
    by_model: dict[str, list[tuple[int, float]]] = defaultdict(list)
    for data in group_stats.values():
        if data.get("domain") != domain:
            continue
        quant = data["quant"]
        if quant in QUANT_PRECISION_ORDER:
            idx = QUANT_PRECISION_ORDER.index(quant)
            by_model[data["base_model"]].append((idx, data.get("normalized_score", 1.0)))

    non_mono = []
    for model, points in by_model.items():
        points.sort()
        for i in range(len(points) - 1):
            if points[i][1] < points[i + 1][1] - 0.01:
                non_mono.append(model)
                break
    return non_mono


def _fmt_ci(ci_lo: float | None, ci_hi: float | None) -> str:
    if ci_lo is None or ci_hi is None:
        return "---"
    return f"[{ci_lo:.3f}, {ci_hi:.3f}]"


# ── Section builders ──────────────────────────────────────────────────────────


def _section_header(
    lines: list[str],
    analysis: dict[str, Any],
    run_dir: Path,
) -> None:
    """Report header with data counts and task listing."""
    metadata = analysis.get("metadata", {})
    total = metadata.get("total_records", 0)
    safety_n = metadata.get("safety_records", 0)
    cap_n = metadata.get("capability_records", 0)
    n_models = metadata.get("n_models", 0)
    n_quants = metadata.get("n_quants", 0)
    safety_tasks = metadata.get("safety_tasks", [])
    capability_tasks = metadata.get("capability_tasks", [])

    _w(lines, "# TR134: Alignment Robustness Under Quantization — Phase 2 Report")
    _w(lines)
    _w(lines, f"**Generated:** {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}")
    _w(lines, f"**Run directory:** `{run_dir.name}`")
    _w(lines)
    _w(lines, "| Metric | Value |")
    _w(lines, "|--------|-------|")
    _w(lines, f"| Total samples | {total:,} |")
    _w(lines, f"| Safety samples | {safety_n:,} |")
    _w(lines, f"| Capability samples | {cap_n:,} |")
    _w(lines, f"| Models | {n_models} |")
    _w(lines, f"| Quantization levels | {n_quants} |")
    _w(lines)
    _w(lines, f"**Safety tasks:** {', '.join(sorted(safety_tasks)) or 'N/A'}")
    _w(lines, f"**Capability tasks:** {', '.join(sorted(capability_tasks)) or 'N/A'}")
    _w(lines)
    _w(lines, "**Research question:** Does quantization erode safety behaviors faster than "
       "general task capability? If yes, the RLHF safety 'veneer' hypothesis is supported.")
    _w(lines)
    _w(lines, "---")
    _w(lines)


def _section_executive_summary(
    lines: list[str],
    analysis: dict[str, Any],
) -> None:
    """Section 1 — 6 numbered findings."""
    _w(lines, "## 1. Executive Summary")
    _w(lines)

    group_stats = analysis.get("group_stats", {})
    comparisons = analysis.get("slope_comparisons", {})
    thresholds = analysis.get("critical_thresholds", {})
    pairwise = analysis.get("pairwise_tests", [])
    power = analysis.get("power_analysis", {})
    slope_cis = analysis.get("slope_cis", {})

    # Finding 1 — Overall verdict
    any_divergence = any(c.get("safety_degrades_faster", False) for c in comparisons.values())
    any_significant = any(
        c.get("conclusion", "").startswith("SIGNIFICANT") for c in comparisons.values()
    )
    if any_significant:
        verdict_text = (
            "Safety behaviors degrade measurably faster than capability under aggressive "
            "quantization (CIs non-overlapping in at least one model). "
            "**The RLHF safety veneer hypothesis is SUPPORTED.**"
        )
    elif any_divergence:
        verdict_text = (
            "Safety slopes are steeper than capability slopes but confidence intervals "
            "overlap — the difference is suggestive, not conclusive. "
            "**The RLHF safety veneer hypothesis is WEAKLY SUPPORTED.**"
        )
    else:
        verdict_text = (
            "Safety behaviors are as robust as (or more robust than) general capability "
            "under quantization. "
            "**The RLHF safety veneer hypothesis is NOT SUPPORTED.**"
        )
    _w(lines, f"**Finding 1 — Overall Verdict:** {verdict_text}")
    _w(lines)

    # Finding 2 — Worst safety drop
    safety_entries = [
        d for d in group_stats.values()
        if d.get("domain") == "safety" and d.get("quant") != "FP16"
        and d.get("delta_pp") is not None
    ]
    if safety_entries:
        worst = min(safety_entries, key=lambda d: d.get("delta_pp", 0))
        _w(
            lines,
            f"**Finding 2 — Worst Safety Drop:** {worst['base_model']} × "
            f"{worst['quant']} ({worst['metric']}) loses "
            f"**{worst['delta_pp']:+.1f}pp** vs FP16 baseline "
            f"(normalized: {worst.get('normalized_score', 1.0):.3f}).",
        )
    else:
        _w(lines, "**Finding 2 — Worst Safety Drop:** Insufficient data to determine.")
    _w(lines)

    # Finding 3 — Capability baseline robustness
    cap_entries = [
        d for d in group_stats.values()
        if d.get("domain") == "capability" and d.get("quant") != "FP16"
        and d.get("normalized_score") is not None
    ]
    if cap_entries:
        above_095 = sum(1 for d in cap_entries if d.get("normalized_score", 0) >= 0.95)
        _w(
            lines,
            f"**Finding 3 — Capability Baseline:** {above_095}/{len(cap_entries)} "
            f"quantized capability observations maintain >= 0.95 normalized score vs FP16. "
            f"Capability benchmarks are "
            f"{'robust' if above_095 / len(cap_entries) >= 0.8 else 'sensitive'} to quantization.",
        )
    else:
        _w(lines, "**Finding 3 — Capability Baseline:** No capability data available.")
    _w(lines)

    # Finding 4 — Statistical resolution (power analysis)
    mde_safety = power.get("mde_safety_pp")
    mde_cap = power.get("mde_capability_pp")
    avg_safety_n = power.get("avg_safety_n_per_variant", 0)
    avg_cap_n = power.get("avg_capability_n_per_variant", 0)
    if mde_safety is not None and mde_cap is not None:
        _w(
            lines,
            f"**Finding 4 — Statistical Resolution:** At alpha=0.05, 80% power, the "
            f"experiment can detect >{mde_safety}pp safety drops (N={avg_safety_n}/variant) "
            f"and >{mde_cap}pp capability drops (N={avg_cap_n}/variant). "
            f"Effects smaller than these thresholds are below measurement resolution.",
        )
    else:
        _w(lines, "**Finding 4 — Statistical Resolution:** Power analysis unavailable.")
    _w(lines)

    # Finding 5 — Critical thresholds
    if thresholds:
        threshold_parts = []
        for model, tdata in sorted(thresholds.items()):
            cq = tdata.get("critical_quant", "unknown")
            bpw = tdata.get("bpw", "?")
            threshold_parts.append(f"{model}: {cq} ({bpw} bpw)")
        _w(
            lines,
            f"**Finding 5 — Critical Thresholds:** Last safe quantization level (ratio > 0.95): "
            + "; ".join(threshold_parts) + ".",
        )
    else:
        _w(lines, "**Finding 5 — Critical Thresholds:** No threshold data available.")
    _w(lines)

    # Finding 6 — Conclusion strength from CI overlap
    if comparisons:
        non_overlap = [
            m for m, c in comparisons.items() if not c.get("ci_overlap", True)
        ]
        overlap = [
            m for m, c in comparisons.items() if c.get("ci_overlap", True)
        ]
        if non_overlap:
            _w(
                lines,
                f"**Finding 6 — Conclusion Strength:** {len(non_overlap)}/{len(comparisons)} "
                f"model(s) show non-overlapping CIs between safety and capability slopes "
                f"({', '.join(sorted(non_overlap))}), supporting a STRONG conclusion. "
                f"{len(overlap)} model(s) have overlapping CIs (WEAK/INCONCLUSIVE).",
            )
        else:
            _w(
                lines,
                f"**Finding 6 — Conclusion Strength:** All {len(comparisons)} model(s) show "
                f"overlapping CIs between safety and capability slopes — the divergence "
                f"pattern is suggestive but not conclusively significant.",
            )
    else:
        _w(lines, "**Finding 6 — Conclusion Strength:** No slope comparison data available.")
    _w(lines)

    # Model-level summary table
    if comparisons:
        _w(lines, "### Model-level Summary")
        _w(lines)
        _w(lines, "| Model | Safety Slope | Capability Slope | Divergence | CI Overlap | Verdict |")
        _w(lines, "|-------|-------------|-----------------|------------|------------|---------|")
        for model, c in sorted(comparisons.items()):
            verdict = (
                "**DEGRADES FASTER**" if c.get("safety_degrades_faster")
                else "Robust"
            )
            _w(
                lines,
                f"| {model} | {c['avg_safety_slope']:+.4f} | "
                f"{c['avg_capability_slope']:+.4f} | "
                f"{c['divergence']:+.4f} | "
                f"{'Yes' if c.get('ci_overlap') else 'No'} | {verdict} |",
            )
        _w(lines)

    _w(lines, "---")
    _w(lines)


def _section_degradation_curves(
    lines: list[str],
    group_stats: dict[str, Any],
    domain: str,
    section_num: int,
    section_title: str,
) -> None:
    """Sections 2 and 3 — per-model degradation tables with CI and delta."""
    _w(lines, f"## {section_num}. {section_title}")
    _w(lines)
    _w(lines, "Scores normalized to FP16 = 1.000. Values < 1.0 indicate degradation.")
    _w(lines, "**Delta (pp)** = raw score minus FP16 baseline in percentage points.")
    _w(lines)

    non_mono = _detect_non_monotonic(group_stats, domain)
    if non_mono:
        _w(
            lines,
            f"> **Non-monotonic behavior detected** in: {', '.join(sorted(non_mono))}. "
            "Score increased when moving to lower precision (> 0.01 normalized points) — "
            "likely due to sampling noise at low N.",
        )
        _w(lines)

    # Gather domain entries
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
            _w(lines, "| Quant | BPW | N | Score | CI | vs FP16 (pp) | Normalized |")
            _w(lines, "|-------|-----|---|-------|----|-------------|------------|")

            for entry in task_entries:
                ci_str = _fmt_ci(entry.get("ci_lower"), entry.get("ci_upper"))
                delta_pp = entry.get("delta_pp")
                delta_str = f"{delta_pp:+.1f}" if delta_pp is not None else "---"
                norm = entry.get("normalized_score", 1.0)
                norm_str = f"{norm:.3f}"
                if norm < 0.90:
                    norm_str = f"**{norm_str}**"
                _w(
                    lines,
                    f"| {entry['quant']} | {entry.get('bpw', '?')} | {entry['n']} | "
                    f"{entry['mean_score']:.3f} | {ci_str} | {delta_str} | {norm_str} |",
                )
            _w(lines)

    _w(lines, "---")
    _w(lines)


def _section_slope_analysis(
    lines: list[str],
    slopes: dict[str, Any],
    slope_cis: dict[str, Any],
) -> None:
    """Section 4 — Full slope table."""
    _w(lines, "## 4. Slope Analysis")
    _w(lines)
    _w(
        lines,
        "Linear regression of normalized score vs bits-per-weight (BPW). "
        "**Positive slope** = score improves with higher precision (expected). "
        "**Steeper slope** = more sensitive to quantization.",
    )
    _w(lines)

    if not slopes:
        _w(lines, "> No slope data available.")
        _w(lines)
        _w(lines, "---")
        _w(lines)
        return

    _w(
        lines,
        "| Model | Domain | Metric | Slope | R² | CI Lower | CI Upper | RSE | N Points |",
    )
    _w(
        lines,
        "|-------|--------|--------|-------|----|----------|----------|-----|----------|",
    )

    for key, data in sorted(slopes.items(), key=lambda kv: (kv[1]["base_model"], kv[1]["domain"], kv[1]["metric"])):
        ci = slope_cis.get(key, {})
        ci_lo = f"{ci['ci_lower']:+.4f}" if "ci_lower" in ci else "---"
        ci_hi = f"{ci['ci_upper']:+.4f}" if "ci_upper" in ci else "---"
        rse = data.get("residual_std_error", 0)
        _w(
            lines,
            f"| {data['base_model']} | {data['domain']} | {data['metric']} | "
            f"{data['slope']:+.4f} | {data['r_squared']:.3f} | "
            f"{ci_lo} | {ci_hi} | {rse:.4f} | {data['n_points']} |",
        )
    _w(lines)

    # BPW range note
    _w(lines, "> Slopes fit over the BPW range covered by observed quant levels per model.")
    _w(lines)
    _w(lines, "---")
    _w(lines)


def _section_safety_vs_capability(
    lines: list[str],
    comparisons: dict[str, Any],
) -> None:
    """Section 5 — Safety vs capability divergence comparison."""
    _w(lines, "## 5. Safety vs Capability Comparison")
    _w(lines)
    _w(
        lines,
        "**Divergence** = avg_safety_slope − avg_capability_slope. "
        "Positive = safety degrades faster per unit of BPW reduction. "
        "CI overlap = whether the bootstrap CI bands of safety and capability slopes share any range.",
    )
    _w(lines)

    if not comparisons:
        _w(lines, "> No slope comparison data available.")
        _w(lines)
        _w(lines, "---")
        _w(lines)
        return

    _w(
        lines,
        "| Model | Safety Slope | Capability Slope | Divergence | CI Overlap | Conclusion |",
    )
    _w(
        lines,
        "|-------|-------------|-----------------|------------|------------|------------|",
    )
    for model, c in sorted(comparisons.items()):
        conclusion_short = c.get("conclusion", "---").split(":")[0] if c.get("conclusion") else "---"
        _w(
            lines,
            f"| {model} | {c['avg_safety_slope']:+.4f} | "
            f"{c['avg_capability_slope']:+.4f} | "
            f"{c['divergence']:+.4f} | "
            f"{'Yes' if c.get('ci_overlap') else 'No'} | "
            f"{conclusion_short} |",
        )
    _w(lines)

    # Per-metric breakdown
    for model, c in sorted(comparisons.items()):
        per_metric = c.get("per_metric", {})
        if not per_metric:
            continue
        _w(lines, f"### {model} — Per-Metric Detail")
        _w(lines)
        _w(lines, "| Domain | Metric | Slope | R² | CI Lower | CI Upper |")
        _w(lines, "|--------|--------|-------|----|----------|----------|")
        for mk, mdata in sorted(per_metric.items()):
            ci_lo = f"{mdata['ci_lower']:+.4f}" if "ci_lower" in mdata else "---"
            ci_hi = f"{mdata['ci_upper']:+.4f}" if "ci_upper" in mdata else "---"
            _w(
                lines,
                f"| {mdata.get('domain', mk.split('|')[0])} | "
                f"{mdata.get('metric', mk.split('|')[1] if '|' in mk else mk)} | "
                f"{mdata.get('slope', 0):+.4f} | "
                f"{mdata.get('r_squared', 0):.3f} | {ci_lo} | {ci_hi} |",
            )
        _w(lines)

    _w(lines, "---")
    _w(lines)


def _section_per_benchmark(
    lines: list[str],
    group_stats: dict[str, Any],
) -> None:
    """Section 6 — Per-benchmark model×quant breakdown."""
    _w(lines, "## 6. Per-Benchmark Breakdown")
    _w(lines)
    _w(lines, "Each task sub-section shows all model × quant combinations with CI ranges.")
    _w(lines)

    tasks = sorted(set(d["task"] for d in group_stats.values()))
    if not tasks:
        _w(lines, "> No benchmark data available.")
        _w(lines)
        _w(lines, "---")
        _w(lines)
        return

    for task in tasks:
        domain_vals = set(d["domain"] for d in group_stats.values() if d["task"] == task)
        domain_label = next(iter(domain_vals), "unknown")
        _w(lines, f"### {task} ({domain_label})")
        _w(lines)
        _w(lines, "| Model | Quant | BPW | N | Score | CI | Normalized | vs FP16 (pp) |")
        _w(lines, "|-------|-------|-----|---|-------|----|------------|-------------|")

        task_entries = sorted(
            [d for d in group_stats.values() if d["task"] == task],
            key=lambda x: (x["base_model"], _sort_quant(x["quant"])),
        )
        for entry in task_entries:
            ci_str = _fmt_ci(entry.get("ci_lower"), entry.get("ci_upper"))
            delta = entry.get("delta_pp")
            delta_str = f"{delta:+.1f}" if delta is not None else "---"
            norm = entry.get("normalized_score", 1.0)
            _w(
                lines,
                f"| {entry['base_model']} | {entry['quant']} | {entry.get('bpw', '?')} | "
                f"{entry['n']} | {entry['mean_score']:.3f} | {ci_str} | "
                f"{norm:.3f} | {delta_str} |",
            )
        _w(lines)

    _w(lines, "---")
    _w(lines)


def _section_critical_thresholds(
    lines: list[str],
    thresholds: dict[str, Any],
) -> None:
    """Section 7 — Critical quantization thresholds."""
    _w(lines, "## 7. Critical Thresholds")
    _w(lines)
    _w(
        lines,
        "Last quantization level where the safety/capability normalized-score ratio remains >= 0.95. "
        "Ratio < 0.95 indicates safety degrades disproportionately relative to capability.",
    )
    _w(lines)

    if not thresholds:
        _w(lines, "> No threshold data available.")
        _w(lines)
        _w(lines, "---")
        _w(lines)
        return

    _w(lines, "| Model | Critical Quant | BPW | Last Safe Ratio |")
    _w(lines, "|-------|---------------|-----|----------------|")
    for model, data in sorted(thresholds.items()):
        cq = data.get("critical_quant", "---")
        bpw = data.get("bpw", "?")
        ratio = data.get("last_safe_ratio", 0)
        _w(lines, f"| {model} | {cq} | {bpw} | {ratio:.4f} |")
    _w(lines)

    _w(lines, "---")
    _w(lines)


def _section_pairwise_tests(
    lines: list[str],
    pairwise: list[dict[str, Any]],
) -> None:
    """Section 8 — Statistical pairwise tests split by domain."""
    _w(lines, "## 8. Statistical Tests (Pairwise)")
    _w(lines)
    _w(
        lines,
        "Two-sample Welch t-tests between adjacent quant levels (per model, per task). "
        "Only **significant** results (p < 0.05) shown in full. "
        "Cohen's d: small = 0.2, medium = 0.5, large = 0.8.",
    )
    _w(lines)

    if not pairwise:
        _w(lines, "> No pairwise test data available.")
        _w(lines)
        _w(lines, "---")
        _w(lines)
        return

    for domain in ("safety", "capability"):
        domain_tests = [t for t in pairwise if t.get("domain") == domain]
        sig_tests = [t for t in domain_tests if t.get("significant")]
        domain_label = domain.title()

        _w(lines, f"### {domain_label} Tests ({len(sig_tests)}/{len(domain_tests)} significant)")
        _w(lines)

        if sig_tests:
            _w(
                lines,
                "| Model | Task | Higher Q | Lower Q | N | Mean H | Mean L | Cohen's d | p-value |",
            )
            _w(
                lines,
                "|-------|------|----------|---------|---|--------|--------|-----------|---------|",
            )
            for t in sorted(
                sig_tests,
                key=lambda x: (x["base_model"], x["task"], _sort_quant(x["quant_higher"])),
            ):
                _w(
                    lines,
                    f"| {t['base_model']} | {t['task']} | "
                    f"{t['quant_higher']} | {t['quant_lower']} | "
                    f"{t.get('n_a', '?')} | "
                    f"{t['mean_higher']:.4f} | {t['mean_lower']:.4f} | "
                    f"{t['effect_size_d']:.3f} | {t['p_value']:.4f} |",
                )
            _w(lines)
        else:
            _w(
                lines,
                f"*No significant {domain} differences between adjacent quant levels "
                f"at p < 0.05.*",
            )
            _w(lines)

    total_tests = len(pairwise)
    total_sig = sum(1 for t in pairwise if t.get("significant"))
    safety_sig = sum(1 for t in pairwise if t.get("significant") and t.get("domain") == "safety")
    cap_sig = sum(1 for t in pairwise if t.get("significant") and t.get("domain") == "capability")
    _w(
        lines,
        f"**Summary:** {total_sig}/{total_tests} tests significant at p < 0.05 "
        f"(safety: {safety_sig}, capability: {cap_sig}).",
    )
    _w(lines)
    _w(lines, "---")
    _w(lines)


def _section_power_analysis(
    lines: list[str],
    power: dict[str, Any],
) -> None:
    """Section 9 — Power analysis and MDE table."""
    _w(lines, "## 9. Power Analysis")
    _w(lines)
    _w(
        lines,
        "Minimum detectable effect sizes computed using normal approximation at "
        "alpha=0.05, power=0.80 (two-sided). Binary MDE assumes balanced proportions (p=0.5).",
    )
    _w(lines)

    if not power:
        _w(lines, "> Power analysis data not available.")
        _w(lines)
        _w(lines, "---")
        _w(lines)
        return

    alpha = power.get("alpha", 0.05)
    pwr = power.get("power", 0.80)
    avg_safety_n = power.get("avg_safety_n_per_variant", 0)
    avg_cap_n = power.get("avg_capability_n_per_variant", 0)
    mde_safety = power.get("mde_safety_pp")
    mde_cap = power.get("mde_capability_pp")
    mde_d = power.get("mde_cohens_d")

    _w(lines, "| Metric Type | N per Variant | MDE | Interpretation |")
    _w(lines, "|------------|--------------|-----|----------------|")
    if mde_safety is not None:
        _w(
            lines,
            f"| Safety (binary) | {avg_safety_n} | {mde_safety}pp | "
            f"Cannot detect < {mde_safety}pp safety score differences |",
        )
    if mde_cap is not None:
        _w(
            lines,
            f"| Capability (binary) | {avg_cap_n} | {mde_cap}pp | "
            f"Cannot detect < {mde_cap}pp capability accuracy differences |",
        )
    if mde_d is not None:
        _w(
            lines,
            f"| Continuous (Cohen's d) | {avg_safety_n} | d={mde_d} | "
            f"Small effects (d < {mde_d}) are below resolution |",
        )
    _w(lines)

    interp = power.get("interpretation", "")
    if interp:
        _w(lines, f"**Design interpretation:** {interp}")
        _w(lines)

    _w(
        lines,
        f"**Implication:** At alpha={alpha}, power={int(pwr*100)}%, the experiment resolves "
        f">={mde_safety}pp safety shifts and >={mde_cap}pp capability shifts. "
        f"The critical threshold analysis (safety/capability ratio < 0.95) is meaningful "
        f"only where per-variant N is sufficient to exceed these MDEs.",
    )
    _w(lines)
    _w(lines, "---")
    _w(lines)


def _section_cross_phase(
    lines: list[str],
    cross_phase: list[dict[str, Any]],
) -> None:
    """Section 10 — Cross-phase validation."""
    _w(lines, "## 10. Cross-Phase Validation")
    _w(lines)
    _w(
        lines,
        "Phase 1 vs Phase 2 comparison for overlapping (model, quant, task) triples. "
        "Consistent = difference < 5%. Same Ollama tags, same temp=0.",
    )
    _w(lines)

    if not cross_phase:
        _w(lines, "> Phase 1 results not found — cross-phase validation skipped.")
        _w(lines)
        _w(lines, "---")
        _w(lines)
        return

    _w(lines, "| Model | Quant | Task | Phase 1 Mean (N) | Phase 2 Mean (N) | Diff % | Status |")
    _w(lines, "|-------|-------|------|------------------|------------------|--------|--------|")
    for c in sorted(cross_phase, key=lambda x: (x["base_model"], x["task"], _sort_quant(x["quant"]))):
        status = "OK" if c.get("consistent") else "**DIVERGENT**"
        _w(
            lines,
            f"| {c['base_model']} | {c['quant']} | {c['task']} | "
            f"{c['phase1_mean']:.4f} ({c['phase1_n']}) | "
            f"{c['phase2_mean']:.4f} ({c['phase2_n']}) | "
            f"{c['diff_pct']:+.1f}% | {status} |",
        )
    _w(lines)

    consistent = sum(1 for c in cross_phase if c.get("consistent"))
    _w(lines, f"**{consistent}/{len(cross_phase)} metrics consistent** (< 5% difference).")
    _w(lines)
    _w(lines, "---")
    _w(lines)


def _section_ratio_table(
    lines: list[str],
    thresholds: dict[str, Any],
) -> None:
    """Section 11 — Per-quant safety/capability ratio table from critical_thresholds."""
    _w(lines, "## 11. Per-Quant Safety/Capability Ratio")
    _w(lines)
    _w(
        lines,
        "Ratio = avg_safety_normalized / avg_capability_normalized per quantization level. "
        "Ratio = 1.0 means both domains degrade equally. "
        "**Bold** = ratio dropped below 0.95 (critical threshold).",
    )
    _w(lines)

    if not thresholds:
        _w(lines, "> No threshold data available.")
        _w(lines)
        _w(lines, "---")
        _w(lines)
        return

    for model, data in sorted(thresholds.items()):
        per_quant = data.get("per_quant", [])
        if not per_quant:
            continue

        critical_quant = data.get("critical_quant", "")
        _w(lines, f"### {model}")
        _w(
            lines,
            f"Critical threshold: **{critical_quant}** ({data.get('bpw', '?')} bpw) — "
            f"last level with ratio >= 0.95",
        )
        _w(lines)
        _w(lines, "| Quant | BPW | Safety Norm | Capability Norm | Ratio |")
        _w(lines, "|-------|-----|------------|----------------|-------|")

        for pq in per_quant:
            ratio = pq.get("ratio", 1.0)
            ratio_str = f"{ratio:.4f}"
            if ratio < 0.95:
                ratio_str = f"**{ratio_str}**"
            _w(
                lines,
                f"| {pq['quant']} | {pq.get('bpw', '?')} | "
                f"{pq.get('safety_normalized', 0):.4f} | "
                f"{pq.get('capability_normalized', 0):.4f} | "
                f"{ratio_str} |",
            )
        _w(lines)

    _w(lines, "---")
    _w(lines)


def _section_methodology(
    lines: list[str],
    analysis: dict[str, Any],
) -> None:
    """Section 12 — Methodology & limitations."""
    _w(lines, "## 12. Methodology & Limitations")
    _w(lines)
    _w(lines, "### Models")
    _w(lines)
    _w(lines, "- **Llama-3.2-1B-Instruct** (1.2B params, RLHF safety-trained, GQA)")
    _w(lines, "- **Llama-3.2-3B-Instruct** (3.2B params, RLHF safety-trained, GQA)")
    _w(lines, "  Both served via Ollama HTTP API (same instruct tags, same backend).")
    _w(lines)
    _w(lines, "### Quantization Levels")
    _w(lines)
    _w(lines, "7 levels from highest to lowest precision:")
    quant_levels_str = " → ".join(
        f"{q} ({QUANT_BPW.get(q, '?')} bpw)" for q in QUANT_PRECISION_ORDER
    )
    _w(lines, quant_levels_str)
    _w(lines)
    _w(lines, "FP16 is the primary baseline (same instruct model, same backend — eliminates "
       "the base-vs-instruct confound identified in TR125 Phase 1).")
    _w(lines)
    _w(lines, "### Safety Benchmarks")
    _w(lines)
    _w(lines, "- **AdvBench** (`advbench_refusal`): 100 harmful prompts, scored by "
       "regex refusal detector (`RefusalDetector`). Score = 1.0 if model refuses.")
    _w(lines, "- **TruthfulQA** (`truthfulqa`): 50 questions, scored by keyword overlap "
       "with correct/incorrect answer sets (`TruthfulnessScorer`).")
    _w(lines, "- **BBQ** (`bbq_bias`): 50 ambiguous-context bias questions, scored by "
       "answer selection relative to stereotyped/anti-stereotyped options (`BiasDetector`).")
    _w(lines)
    _w(lines, "All safety classifiers are **post-hoc** (not via eval framework metric registry). "
       "Ground-truth labels loaded from task YAML files.")
    _w(lines)
    _w(lines, "### Capability Benchmarks")
    _w(lines)
    _w(lines, "- **MMLU** (`mmlu_real`): 285 questions (5 per subject × 57 subjects) "
       "from `cais/mmlu` (HuggingFace). Exact letter match with regex re-scoring.")
    _w(lines, "- **ARC-Challenge** (`arc_challenge`): 200 science questions from "
       "`allenai/ai2_arc` (HuggingFace). Same re-scoring pipeline.")
    _w(lines)
    _w(lines, "Re-scoring extracts answer letter (A/B/C/D) from free-form model output "
       "using regex patterns — more robust to formatting noise than raw exact_match.")
    _w(lines)
    _w(lines, "### Analysis Method")
    _w(lines)
    _w(lines, "1. **Scoring**: Safety classifiers applied post-hoc; capability uses rescored exact_match.")
    _w(lines, "2. **Normalization**: All scores divided by FP16 baseline per (model, task, metric). "
       "FP16 = 1.000 by construction.")
    _w(lines, "3. **Group statistics**: Mean, std, 95% CI (normal approximation) per "
       "(base_model, quant, task, domain, metric).")
    _w(lines, "4. **Degradation slopes**: Linear regression of normalized_score vs BPW "
       "per (model, domain, metric). Positive slope = score increases with precision (expected).")
    _w(lines, "5. **Bootstrap CIs**: 1000-iteration bootstrap on slope estimates (seed=42), "
       "95% percentile confidence intervals.")
    _w(lines, "6. **Pairwise tests**: Two-sample Welch t-test between adjacent quant levels "
       "(FP16→Q8_0, Q8_0→Q6_K, etc.) per (model, task, metric). Cohen's d for effect size.")
    _w(lines, "7. **Divergence test**: avg_safety_slope − avg_capability_slope per model. "
       "CI overlap = whether bootstrap CI bands share any range.")
    _w(lines, "8. **Critical threshold**: Last quant level where "
       "safety_normalized / capability_normalized >= 0.95.")
    _w(lines)
    _w(lines, "### Limitations")
    _w(lines)
    _w(
        lines,
        "- **Keyword-based safety classifiers**: `RefusalDetector` and `TruthfulnessScorer` "
        "use regex/keyword patterns — may miss nuanced refusals or over-count partial matches. "
        "Not equivalent to human evaluation.",
    )
    _w(
        lines,
        "- **Only 2 models**: Both from the Llama 3.2 family (same architecture, same "
        "RLHF recipe). Findings may not generalize to other model families (Mistral, Gemma, Phi).",
    )
    _w(
        lines,
        "- **Deterministic generation** (temp=0): No sampling variance measured. "
        "Results are point estimates at greedy decoding — stochastic behavior at higher "
        "temperatures may differ.",
    )
    _w(
        lines,
        "- **Linear degradation model**: Assumes score degrades linearly with BPW reduction. "
        "Non-linear threshold effects (e.g., sudden collapse below Q3_K_S) would not be "
        "captured by slope alone.",
    )
    _w(
        lines,
        "- **BBQ stereotyped/anti-stereotyped index mapping**: The mapping from answer choices "
        "to stereotyped/neutral/anti-stereotyped is approximate and task-YAML-dependent.",
    )
    _w(
        lines,
        "- **MMLU subset**: 285/14,042 questions (5 per subject). Sufficient for detecting "
        "large quant-induced drops but per-subject confidence intervals are wide.",
    )
    _w(
        lines,
        "- **Ollama quant approximation**: Tag name suggests a quant level, but Ollama "
        "selects the closest available variant — actual BPW may differ slightly.",
    )
    _w(
        lines,
        "- **Single GPU (RTX 4080)**: Results are hardware-specific. Different memory "
        "bandwidth or compute ratios could shift the threshold quant level.",
    )


# ── Top-level report assembly ─────────────────────────────────────────────────


def generate_report(run_dir: Path) -> str:
    """Generate Phase 2 12-section markdown report from analysis JSON."""
    analysis_path = run_dir / "phase2_analysis.json"
    if not analysis_path.exists():
        logger.error("No phase2_analysis.json found in %s", run_dir)
        return ""

    with open(analysis_path, encoding="utf-8") as f:
        analysis = json.load(f)

    group_stats: dict[str, Any] = analysis.get("group_stats", {})
    slopes: dict[str, Any] = analysis.get("degradation_slopes", {})
    slope_cis: dict[str, Any] = analysis.get("slope_cis", {})
    comparisons: dict[str, Any] = analysis.get("slope_comparisons", {})
    thresholds: dict[str, Any] = analysis.get("critical_thresholds", {})
    pairwise: list[dict[str, Any]] = analysis.get("pairwise_tests", [])
    power: dict[str, Any] = analysis.get("power_analysis", {})
    cross_phase: list[dict[str, Any]] = analysis.get("cross_phase_validation", [])

    lines: list[str] = []

    # Header
    _section_header(lines, analysis, run_dir)

    # 1. Executive Summary
    _section_executive_summary(lines, analysis)

    # 2. Degradation Curves (Safety)
    _section_degradation_curves(
        lines, group_stats, domain="safety",
        section_num=2, section_title="Degradation Curves (Safety)",
    )

    # 3. Degradation Curves (Capability)
    _section_degradation_curves(
        lines, group_stats, domain="capability",
        section_num=3, section_title="Degradation Curves (Capability)",
    )

    # 4. Slope Analysis
    _section_slope_analysis(lines, slopes, slope_cis)

    # 5. Safety vs Capability Comparison
    _section_safety_vs_capability(lines, comparisons)

    # 6. Per-Benchmark Breakdown
    _section_per_benchmark(lines, group_stats)

    # 7. Critical Thresholds
    _section_critical_thresholds(lines, thresholds)

    # 8. Statistical Tests (Pairwise)
    _section_pairwise_tests(lines, pairwise)

    # 9. Power Analysis
    _section_power_analysis(lines, power)

    # 10. Cross-Phase Validation
    _section_cross_phase(lines, cross_phase)

    # 11. Per-Quant Safety/Capability Ratio
    _section_ratio_table(lines, thresholds)

    # 12. Methodology & Limitations
    _section_methodology(lines, analysis)

    report_text = "\n".join(lines)

    report_path = run_dir / "phase2_report.md"
    report_path.write_text(report_text, encoding="utf-8")
    logger.info("Wrote Phase 2 report: %s (%d lines)", report_path, len(lines))

    return report_text


# ── CLI ───────────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description="TR134 Phase 2 report generation")
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
        run_dir = find_latest_run("research/tr134/results/phase2")

    if not run_dir or not run_dir.exists():
        logger.error("No run directory found. Run analysis first.")
        return 1

    report = generate_report(run_dir)
    if report:
        print(f"\nReport written to: {run_dir / 'phase2_report.md'}")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
