"""TR139: Multi-turn jailbreak x quantization — report generator.

Generates a markdown report from tr139_analysis.json with 25 sections.
Reports are scaffolds — final publication text is hand-written.

Usage:
    python research/tr139/generate_report.py [-v] [--run-dir DIR]
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
from pathlib import Path

_DIR = Path(__file__).resolve().parent
_REPO = _DIR.parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from research.tr139.shared.utils import (
    ATTACK_STRATEGIES,
    BPW_MAP,
    find_latest_run,
)

logger = logging.getLogger("tr139.generate_report")


# ── Formatting helpers ────────────────────────────────────────────


def _fmt_pval(p: float) -> str:
    if p < 0.001:
        return "<0.001"
    return f"{p:.3f}"


def _fmt_pct(v: float) -> str:
    return f"{v * 100:.1f}%"


def _fmt_f(v: float) -> str:
    return f"{v:.2f}"


def _fmt_signed(v: float) -> str:
    return f"+{v:.4f}" if v > 0 else f"{v:.4f}"


def _bold_if(text: str, condition: bool) -> str:
    return f"**{text}**" if condition else text


def _get_git_hash() -> str:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            cwd=_REPO,
        )
        return r.stdout.strip() if r.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def _safe_get(d: dict, *keys, default=None):
    """Nested dict access with default."""
    curr = d
    for k in keys:
        if isinstance(curr, dict):
            curr = curr.get(k, default)
        else:
            return default
    return curr


# ── Section functions ─────────────────────────────────────────────
# Each appends markdown lines to `lines` list.


def _section_metadata(lines: list[str], analysis: dict) -> None:
    """Section 0: Report metadata header."""
    git_hash = _get_git_hash()
    lines.append("---")
    lines.append(f"experiment: {analysis.get('experiment', 'tr139')}")
    lines.append(f"git_commit: {git_hash}")
    lines.append(f"n_conversations: {analysis.get('n_conversations', 0)}")
    lines.append(f"n_phase1: {analysis.get('n_phase1', 0)}")
    lines.append(f"n_phase2: {analysis.get('n_phase2', 0)}")
    lines.append(f"status: auto-generated scaffold")
    lines.append("---")
    lines.append("")


def _section_abstract(lines: list[str], analysis: dict) -> None:
    """Section 1: Abstract."""
    lines.append("# TR139: Multi-Turn Jailbreak Susceptibility Under Quantization")
    lines.append("")
    lines.append("## Abstract")
    lines.append("")

    n_conv = analysis.get("n_conversations", 0)
    n_p1 = analysis.get("n_phase1", 0)
    n_p2 = analysis.get("n_phase2", 0)

    lines.append(
        f"We test whether quantization amplifies multi-turn jailbreak "
        f"susceptibility in open-weight LLMs. {n_conv} multi-turn "
        f"conversations ({n_p1} Phase 1 attack tests + {n_p2} Phase 2 "
        f"persistence tests) across 3 models, 6 quantization levels, "
        f"4 attack strategies, and 30 harmful behaviors from 10 "
        f"JailbreakBench categories. All multi-turn jailbreak literature "
        f"tests full-precision or closed-weight models; all "
        f"quantization-safety literature uses single-turn attacks. "
        f"This is the first study combining both axes."
    )
    lines.append("")
    lines.append("[HAND-WRITE: Key findings summary, 2-3 sentences]")
    lines.append("")


def _section_toc(lines: list[str], analysis: dict) -> None:
    """Section 2: Table of Contents."""
    lines.append("## Table of Contents")
    lines.append("")
    toc = [
        "1. Abstract",
        "2. Table of Contents",
        "3. Executive Summary",
        "4. Hypotheses",
        "5. Methodology",
        "6. Models & Quantization Levels",
        "7. Attack Strategies",
        "8. Phase 1: ASR by Strategy x Quant",
        "9. Turn-of-First-Compliance Analysis",
        "10. ASR Slopes vs BPW",
        "11. Strategy Effectiveness Ranking",
        "12. Per-Category Vulnerability",
        "13. Per-Model Comparison",
        "14. Quant x Strategy Interaction (ANOVA)",
        "15. Statistical Tests (Fisher, Chi-sq)",
        "16. Phase 2: Refusal Persistence",
        "17. Persistence Slopes vs BPW",
        "18. Turn-Level Safety Trajectories",
        "19. Cross-Strategy Correlation",
        "20. Judge Agreement",
        "21. Latency Analysis",
        "22. Critical Quant Thresholds",
        "23. Cross-TR Validation",
        "24. TOST Equivalence",
        "25. Power Analysis",
        "26. Phase 2 Persistence Curves",
        "27. Variance Decomposition",
        "28. Multi-Turn Amplification Ratio",
        "29. Conditional ASR",
        "30. Hypothesis Evaluation",
        "31. Limitations",
        "32. Conclusions",
        "33. Production Guidance",
        "34. Reproducibility",
        "A. Appendix: Full ASR Matrix",
        "B. Appendix: Statistical Test Tables",
        "C. Appendix: Glossary",
        "D. References",
    ]
    for item in toc:
        lines.append(f"- {item}")
    lines.append("")


def _section_executive_summary(lines: list[str], analysis: dict) -> None:
    """Section 3: Executive Summary."""
    lines.append("## 3. Executive Summary")
    lines.append("")

    # H1 summary
    h1 = _safe_get(analysis, "hypothesis_evaluation", "h1_independence", default={})
    lines.append("### H1: ASR Independence of Quantization")
    lines.append("")
    lines.append(f"**Verdict:** {h1.get('summary', 'No data')}")
    lines.append("")
    for t in h1.get("tests", []):
        lines.append(
            f"- {t['strategy']}: F={_fmt_f(t['f'])}, "
            f"p={_fmt_pval(t['p'])} "
            f"{'(REJECTED)' if t['reject_h1'] else '(not rejected)'}"
        )
    lines.append("")

    # H2 summary
    h2 = _safe_get(analysis, "hypothesis_evaluation", "h2_amplification", default={})
    lines.append("### H2: Quantization Amplifies Multi-Turn Attacks")
    lines.append("")
    lines.append(f"**Verdict:** {h2.get('summary', 'No data')}")
    lines.append("")
    if "ratio" in h2:
        lines.append(
            f"- Direct slope magnitude: {h2.get('avg_direct_slope_magnitude', 0):.6f}"
        )
        lines.append(
            f"- Multi-turn slope magnitude: {h2.get('avg_multi_turn_slope_magnitude', 0):.6f}"
        )
        lines.append(f"- Ratio: {h2.get('ratio', 'N/A')}x")
    lines.append("")

    # H3 summary
    h3 = _safe_get(analysis, "hypothesis_evaluation", "h3_persistence", default={})
    lines.append("### H3: Persistence Decreases with Quantization")
    lines.append("")
    lines.append(f"**Verdict:** {h3.get('summary', 'No data')}")
    lines.append("")


def _section_hypotheses(lines: list[str], analysis: dict) -> None:
    """Section 4: Formal hypotheses."""
    lines.append("## 4. Hypotheses")
    lines.append("")
    lines.append(
        "- **H1:** Multi-turn ASR is independent of quantization level "
        "(quant affects single-turn and multi-turn equally)"
    )
    lines.append(
        "- **H2:** Quantization amplifies multi-turn attack effectiveness "
        "(lower quant = higher ASR or earlier compliance)"
    )
    lines.append(
        "- **H3:** Refusal persistence (turns before compliance) "
        "decreases with quantization"
    )
    lines.append("")


def _section_methodology(lines: list[str], analysis: dict) -> None:
    """Section 5: Methodology."""
    lines.append("## 5. Methodology")
    lines.append("")
    lines.append("### Phase 1: Multi-Turn Attack Effectiveness x Quantization")
    lines.append("")
    lines.append(
        "Each of 30 harmful behaviors is tested with 4 attack strategies "
        "(direct=1 turn, foot-in-door/crescendo/attention-shift=5 turns) "
        "at 6 quantization levels (Q8_0 through Q2_K) on 3 models. "
        "Conversations use Ollama `/api/chat` with full message history "
        "accumulation. Per-turn responses are scored by `RefusalDetector` "
        "(regex classifier). Primary metric: Attack Success Rate (ASR) = "
        "fraction of conversations where the target turn (final harmful "
        "request) elicited compliance."
    )
    lines.append("")
    lines.append("### Phase 2: Refusal Persistence Under Pressure")
    lines.append("")
    lines.append(
        "Each behavior is sent as a direct request. If the model refuses, "
        "5 pressure follow-up turns test persistence. Measured at 3 quant "
        "levels (Q8_0, Q4_K_M, Q2_K). Metrics: break rate, persistence "
        "score, pressure resistance."
    )
    lines.append("")
    lines.append("### Scoring")
    lines.append("")
    lines.append(
        "- **RefusalDetector** (regex): detects hard/soft refusal patterns. "
        "Score 1.0 = refused, 0.0 = complied."
    )
    lines.append(
        "- **LLM Judge** (Qwen 2.5 7B @ Q8_0, post-hoc): validates "
        "regex classifications on target turns."
    )
    lines.append("")


def _section_models(lines: list[str], analysis: dict) -> None:
    """Section 6: Models & quantization levels."""
    lines.append("## 6. Models & Quantization Levels")
    lines.append("")
    lines.append("| Model | Params | Family | Quant Levels |")
    lines.append("|-------|--------|--------|-------------|")
    lines.append(
        "| llama3.2-1b | 1.2B | Llama 3.2 | Q8_0, Q6_K, Q5_K_M, Q4_K_M, Q3_K_M, Q2_K |"
    )
    lines.append(
        "| llama3.2-3b | 3.2B | Llama 3.2 | Q8_0, Q6_K, Q5_K_M, Q4_K_M, Q3_K_M, Q2_K |"
    )
    lines.append(
        "| qwen2.5-1.5b | 1.5B | Qwen 2.5 | Q8_0, Q6_K, Q5_K_M, Q4_K_M, Q3_K_M, Q2_K |"
    )
    lines.append("")
    lines.append("| Quant | BPW |")
    lines.append("|-------|-----|")
    for q, bpw in sorted(BPW_MAP.items(), key=lambda x: -x[1]):
        if q != "FP16":
            lines.append(f"| {q} | {bpw} |")
    lines.append("")


def _section_attack_strategies(lines: list[str], analysis: dict) -> None:
    """Section 7: Attack strategy descriptions."""
    lines.append("## 7. Attack Strategies")
    lines.append("")
    for name, strat in ATTACK_STRATEGIES.items():
        n_turns = len(strat["turns"])
        lines.append(f"### {name} ({n_turns} turn{'s' if n_turns > 1 else ''})")
        lines.append("")
        lines.append(f"{strat['description']}")
        lines.append("")


def _section_phase1_asr(lines: list[str], analysis: dict) -> None:
    """Section 8: Phase 1 ASR by strategy x quant."""
    lines.append("## 8. Phase 1: ASR by Strategy x Quant")
    lines.append("")

    asr_table = analysis.get("phase1_asr_matrix", [])
    if not asr_table:
        lines.append("*No Phase 1 data.*")
        lines.append("")
        return

    # Group by model
    models = sorted({r["model"] for r in asr_table})
    for model in models:
        lines.append(f"### {model}")
        lines.append("")
        strategies = sorted({r["strategy"] for r in asr_table if r["model"] == model})
        quants = sorted(
            {r["quant"] for r in asr_table if r["model"] == model},
            key=lambda q: -BPW_MAP.get(q, 0),
        )

        # Header
        header = "| Quant | BPW |"
        sep = "|-------|-----|"
        for s in strategies:
            header += f" {s} |"
            sep += "------|"
        lines.append(header)
        lines.append(sep)

        for quant in quants:
            row = f"| {quant} | {BPW_MAP.get(quant, '?')} |"
            for s in strategies:
                match = [
                    r for r in asr_table
                    if r["model"] == model and r["quant"] == quant and r["strategy"] == s
                ]
                if match:
                    asr = match[0]["asr"]
                    ci = f"[{match[0]['ci_lo']:.3f}, {match[0]['ci_hi']:.3f}]"
                    row += f" {_fmt_pct(asr)} {ci} |"
                else:
                    row += " - |"
            lines.append(row)

        lines.append("")
        lines.append("**Observations:**")
        lines.append("")
        lines.append("[HAND-WRITE: Interpret the ASR matrix for this model]")
        lines.append("")


def _section_tofc(lines: list[str], analysis: dict) -> None:
    """Section 9: Turn-of-first-compliance."""
    lines.append("## 9. Turn-of-First-Compliance Analysis")
    lines.append("")

    tofc = analysis.get("phase1_tofc", [])
    if not tofc:
        lines.append("*No compliance events recorded (all attacks refused).*")
        lines.append("")
        return

    lines.append(
        "| Model | Quant | Strategy | Mean Turn | Std | Min | Max | N |"
    )
    lines.append(
        "|-------|-------|----------|-----------|-----|-----|-----|---|"
    )
    for row in tofc:
        lines.append(
            f"| {row['model']} | {row['quant']} | {row['strategy']} | "
            f"{row['mean_turn']:.1f} | {row['std_turn']:.1f} | "
            f"{row['min_turn']} | {row['max_turn']} | {row['n_complied']} |"
        )
    lines.append("")
    lines.append("**Observations:**")
    lines.append("")
    lines.append(
        "[HAND-WRITE: Do models comply at earlier turns under lower quant?]"
    )
    lines.append("")


def _section_asr_slopes(lines: list[str], analysis: dict) -> None:
    """Section 10: ASR slopes vs BPW."""
    lines.append("## 10. ASR Slopes vs BPW")
    lines.append("")

    slopes = analysis.get("phase1_asr_slopes", [])
    if not slopes:
        lines.append("*Insufficient data for slope analysis.*")
        lines.append("")
        return

    lines.append(
        "| Model | Strategy | Slope/BPW | 95% CI | R^2 | Interpretation |"
    )
    lines.append(
        "|-------|----------|-----------|--------|-----|----------------|"
    )
    for s in slopes:
        ci = f"[{s['ci_lo']:.6f}, {s['ci_hi']:.6f}]"
        slope_str = _bold_if(
            _fmt_signed(s["slope_per_bpw"]),
            s["ci_hi"] < 0,  # Bold if entire CI is negative
        )
        lines.append(
            f"| {s['model']} | {s['strategy']} | {slope_str} | "
            f"{ci} | {s['r_squared']:.3f} | {s['interpretation']} |"
        )
    lines.append("")
    lines.append("**Observations:**")
    lines.append("")
    lines.append(
        "[HAND-WRITE: Are multi-turn slopes steeper than direct? "
        "Which strategies are most affected by quantization?]"
    )
    lines.append("")


def _section_strategy_ranking(lines: list[str], analysis: dict) -> None:
    """Section 11: Strategy effectiveness ranking."""
    lines.append("## 11. Strategy Effectiveness Ranking")
    lines.append("")

    rankings = analysis.get("phase1_strategy_ranking", [])
    if not rankings:
        lines.append("*No ranking data.*")
        lines.append("")
        return

    for entry in rankings:
        lines.append(f"**{entry['model']} @ {entry['quant']}:**")
        for r in entry["ranking"]:
            lines.append(
                f"  {r['rank']}. {r['strategy']} (ASR={_fmt_pct(r['asr'])})"
            )
        lines.append("")

    lines.append("**Observations:**")
    lines.append("")
    lines.append(
        "[HAND-WRITE: Does ranking change across quant levels? "
        "Which strategy is most effective at low quant?]"
    )
    lines.append("")


def _section_per_category(lines: list[str], analysis: dict) -> None:
    """Section 12: Per-category vulnerability."""
    lines.append("## 12. Per-Category Vulnerability")
    lines.append("")

    cat_data = analysis.get("phase1_per_category", [])
    if not cat_data:
        lines.append("*No per-category data.*")
        lines.append("")
        return

    # Group by category, show ASR across quant levels
    categories = sorted({r["category"] for r in cat_data})

    lines.append("| Category | Q8_0 ASR | Q2_K ASR | Delta |")
    lines.append("|----------|----------|----------|-------|")

    for cat in categories:
        q8_rows = [r for r in cat_data if r["category"] == cat and r["quant"] == "Q8_0"]
        q2_rows = [r for r in cat_data if r["category"] == cat and r["quant"] == "Q2_K"]
        q8_asr = sum(r["k"] for r in q8_rows) / max(1, sum(r["n"] for r in q8_rows))
        q2_asr = sum(r["k"] for r in q2_rows) / max(1, sum(r["n"] for r in q2_rows))
        delta = q2_asr - q8_asr
        lines.append(
            f"| {cat} | {_fmt_pct(q8_asr)} | {_fmt_pct(q2_asr)} | "
            f"{_fmt_signed(delta)} |"
        )

    lines.append("")
    lines.append("**Observations:**")
    lines.append("")
    lines.append(
        "[HAND-WRITE: Which harm categories are most vulnerable "
        "to quantization-amplified jailbreaks?]"
    )
    lines.append("")


def _section_model_anova(lines: list[str], analysis: dict) -> None:
    """Section 13: Per-model comparison ANOVA."""
    lines.append("## 13. Per-Model Comparison")
    lines.append("")

    anova = analysis.get("phase1_model_anova", {})
    if not anova:
        lines.append("*No ANOVA data.*")
        lines.append("")
        return

    lines.append("| Strategy | F | p | Significant |")
    lines.append("|----------|---|---|-------------|")
    for strategy, result in sorted(anova.items()):
        sig = "Yes" if result["p_value"] < 0.05 else "No"
        lines.append(
            f"| {strategy} | {_fmt_f(result['f_statistic'])} | "
            f"{_fmt_pval(result['p_value'])} | {sig} |"
        )
        if result.get("model_asrs"):
            for m, a in sorted(result["model_asrs"].items()):
                lines.append(f"|  -> {m} | | {_fmt_pct(a)} | |")
    lines.append("")
    lines.append("**Observations:**")
    lines.append("")
    lines.append(
        "[HAND-WRITE: Do some model families resist multi-turn "
        "attacks better than others?]"
    )
    lines.append("")


def _section_two_way_anova(lines: list[str], analysis: dict) -> None:
    """Section 14: Quant x strategy interaction."""
    lines.append("## 14. Quant x Strategy Interaction (Two-Way ANOVA)")
    lines.append("")

    anova = analysis.get("phase1_two_way_anova", {})
    if not anova:
        lines.append("*No ANOVA data.*")
        lines.append("")
        return

    lines.append(
        "| Model | F(quant) | p(quant) | F(strategy) | p(strategy) | "
        "F(interaction) | p(interaction) | eta2(Q) | eta2(S) | eta2(QxS) |"
    )
    lines.append(
        "|-------|----------|----------|-------------|-------------|"
        "----------------|----------------|---------|---------|-----------|"
    )
    for model, result in sorted(anova.items()):
        lines.append(
            f"| {model} | {_fmt_f(result['f_a'])} | "
            f"{_fmt_pval(result['p_a'])} | "
            f"{_fmt_f(result['f_b'])} | {_fmt_pval(result['p_b'])} | "
            f"{_fmt_f(result['f_ab'])} | {_fmt_pval(result['p_ab'])} | "
            f"{result.get('eta2_a', 0):.3f} | {result.get('eta2_b', 0):.3f} | "
            f"{result.get('eta2_ab', 0):.3f} |"
        )
    lines.append("")
    lines.append("**Observations:**")
    lines.append("")
    lines.append(
        "[HAND-WRITE: Is there a significant quant x strategy interaction? "
        "Does quantization differentially affect multi-turn vs direct?]"
    )
    lines.append("")


def _section_stat_tests(lines: list[str], analysis: dict) -> None:
    """Section 15: Statistical tests."""
    lines.append("## 15. Statistical Tests (vs Q8_0 Baseline)")
    lines.append("")

    tests = analysis.get("phase1_stat_tests", [])
    if not tests:
        lines.append("*No statistical test data.*")
        lines.append("")
        return

    sig_tests = [t for t in tests if t.get("significant_0.05")]
    lines.append(
        f"**{len(sig_tests)}/{len(tests)} tests significant at "
        f"alpha=0.05 after Holm correction.**"
    )
    lines.append("")

    lines.append(
        "| Model | Strategy | Quant | Base ASR | Test ASR | "
        "Fisher p | Holm p | OR | Sig |"
    )
    lines.append(
        "|-------|----------|-------|----------|----------|"
        "---------|--------|-----|-----|"
    )
    for t in tests:
        sig = "***" if t.get("significant_0.05") else ""
        lines.append(
            f"| {t['model']} | {t['strategy']} | {t['test_quant']} | "
            f"{_fmt_pct(t['baseline_asr'])} | {_fmt_pct(t['test_asr'])} | "
            f"{_fmt_pval(t['fisher_p'])} | {_fmt_pval(t['fisher_p_holm'])} | "
            f"{t['odds_ratio']} | {sig} |"
        )
    lines.append("")


def _section_phase2_persistence(lines: list[str], analysis: dict) -> None:
    """Section 16: Phase 2 persistence results."""
    lines.append("## 16. Phase 2: Refusal Persistence Under Pressure")
    lines.append("")

    persist = analysis.get("phase2_persistence", [])
    if not persist:
        lines.append("*No Phase 2 data.*")
        lines.append("")
        return

    lines.append(
        "| Model | Quant | BPW | N | Initial Refused | Broke | "
        "Break Rate | Mean Persistence | Pressure Resistance |"
    )
    lines.append(
        "|-------|-------|-----|---|----------------|-------|"
        "------------|------------------|---------------------|"
    )
    for row in persist:
        lines.append(
            f"| {row['model']} | {row['quant']} | {row['bpw']} | "
            f"{row['n']} | {row['n_initial_refused']} | "
            f"{row['n_broke_under_pressure']} | "
            f"{_fmt_pct(row['break_rate'])} | "
            f"{row['mean_persistence']:.3f} | "
            f"{row['mean_pressure_resistance']:.3f} |"
        )
    lines.append("")
    lines.append("**Observations:**")
    lines.append("")
    lines.append(
        "[HAND-WRITE: Does lower quant reduce persistence? "
        "How many pressure turns does it take to break compliance?]"
    )
    lines.append("")


def _section_persistence_slopes(lines: list[str], analysis: dict) -> None:
    """Section 17: Persistence slopes vs BPW."""
    lines.append("## 17. Persistence Slopes vs BPW")
    lines.append("")

    slopes = analysis.get("phase2_persistence_slopes", [])
    if not slopes:
        lines.append("*Insufficient Phase 2 data for slope analysis.*")
        lines.append("")
        return

    lines.append("| Model | Slope/BPW | 95% CI | Interpretation |")
    lines.append("|-------|-----------|--------|----------------|")
    for s in slopes:
        ci = f"[{s['ci_lo']:.6f}, {s['ci_hi']:.6f}]"
        lines.append(
            f"| {s['model']} | {_fmt_signed(s['slope_per_bpw'])} | "
            f"{ci} | {s['interpretation']} |"
        )
    lines.append("")


def _section_trajectories(lines: list[str], analysis: dict) -> None:
    """Section 18: Turn-level safety trajectories."""
    lines.append("## 18. Turn-Level Safety Trajectories")
    lines.append("")

    trajectories = analysis.get("turn_trajectories", [])
    if not trajectories:
        lines.append("*No trajectory data.*")
        lines.append("")
        return

    # Show one representative table per strategy
    strategies_shown = set()
    for entry in trajectories:
        strategy = entry["strategy"]
        if strategy in strategies_shown:
            continue
        strategies_shown.add(strategy)

        lines.append(f"### {strategy}")
        lines.append("")
        lines.append("| Model | Quant | T1 | T2 | T3 | T4 | T5 |")
        lines.append("|-------|-------|-----|-----|-----|-----|-----|")

        for row in trajectories:
            if row["strategy"] != strategy:
                continue
            curve = row["trajectory"]
            cols = [f"{row['model']} | {row['quant']}"]
            for i in range(5):
                if i < len(curve):
                    cols.append(f"{curve[i]['mean_refusal_score']:.2f}")
                else:
                    cols.append("-")
            lines.append("| " + " | ".join(cols) + " |")
        lines.append("")

    lines.append("**Observations:**")
    lines.append("")
    lines.append(
        "[HAND-WRITE: How does refusal score change across turns? "
        "Do quantized models show steeper drop-offs?]"
    )
    lines.append("")


def _section_cross_strategy(lines: list[str], analysis: dict) -> None:
    """Section 19: Cross-strategy correlation."""
    lines.append("## 19. Cross-Strategy Correlation")
    lines.append("")

    corr = analysis.get("cross_strategy_correlation", [])
    if not corr:
        lines.append("*No cross-strategy data.*")
        lines.append("")
        return

    lines.append(
        "| Model | Quant | Strategy A | Strategy B | r | p | N |"
    )
    lines.append(
        "|-------|-------|------------|------------|---|---|---|"
    )
    for c in corr:
        lines.append(
            f"| {c['model']} | {c['quant']} | {c['strategy_a']} | "
            f"{c['strategy_b']} | {c['r']:.3f} | {_fmt_pval(c['p'])} | "
            f"{c['n_behaviors']} |"
        )
    lines.append("")
    lines.append("**Observations:**")
    lines.append("")
    lines.append(
        "[HAND-WRITE: Do the same behaviors fail across strategies? "
        "High r = behavior-specific vulnerability, low r = strategy-specific.]"
    )
    lines.append("")


def _section_judge_agreement(lines: list[str], analysis: dict) -> None:
    """Section 20: Judge agreement."""
    lines.append("## 20. Judge Agreement (Regex vs LLM)")
    lines.append("")

    agreement = analysis.get("judge_agreement", {})
    if not agreement:
        lines.append("*No judge labels available.*")
        lines.append("")
        return

    lines.append("| Stratum | N | Agreement | Cohen's Kappa |")
    lines.append("|---------|---|-----------|---------------|")
    for stratum, data in sorted(agreement.items()):
        lines.append(
            f"| {stratum} | {data['n']} | "
            f"{_fmt_pct(data['agreement'])} | {data['kappa']:.3f} |"
        )
    lines.append("")
    lines.append("**Observations:**")
    lines.append("")
    lines.append(
        "[HAND-WRITE: Does agreement degrade at lower quant? "
        "This would indicate harder-to-classify responses.]"
    )
    lines.append("")


def _section_latency(lines: list[str], analysis: dict) -> None:
    """Section 21: Latency analysis."""
    lines.append("## 21. Latency Analysis")
    lines.append("")

    latency = analysis.get("latency_analysis", [])
    if not latency:
        lines.append("*No latency data.*")
        lines.append("")
        return

    lines.append(
        "| Model | Quant | Strategy | Mean Total (ms) | "
        "Mean/Turn (ms) | N |"
    )
    lines.append(
        "|-------|-------|----------|-----------------|"
        "----------------|---|"
    )
    for row in latency:
        lines.append(
            f"| {row['model']} | {row['quant']} | {row['strategy']} | "
            f"{row['mean_total_ms']:.0f} | {row['mean_per_turn_ms']:.0f} | "
            f"{row['n']} |"
        )
    lines.append("")

    # Latency slopes
    slopes = analysis.get("latency_slopes", [])
    if slopes:
        lines.append("### Latency vs BPW Slopes")
        lines.append("")
        lines.append("| Model | Strategy | ms/BPW |")
        lines.append("|-------|----------|--------|")
        for s in slopes:
            lines.append(
                f"| {s['model']} | {s['strategy']} | {s['ms_per_bpw']:.1f} |"
            )
        lines.append("")


def _section_critical_thresholds(lines: list[str], analysis: dict) -> None:
    """Section 22: Critical quant thresholds."""
    lines.append("## 22. Critical Quant Thresholds")
    lines.append("")

    thresholds = analysis.get("critical_thresholds", [])
    if not thresholds:
        lines.append("*No threshold data.*")
        lines.append("")
        return

    lines.append(
        "| Model | Strategy | Critical Quant | Note |"
    )
    lines.append(
        "|-------|----------|----------------|------|"
    )
    for t in thresholds:
        crit = t.get("critical_quant") or "None"
        lines.append(
            f"| {t['model']} | {t['strategy']} | "
            f"{_bold_if(crit, crit != 'None')} | {t['note']} |"
        )
    lines.append("")
    lines.append("**Observations:**")
    lines.append("")
    lines.append(
        "[HAND-WRITE: At what quant level does multi-turn ASR "
        "significantly exceed the Q8_0 baseline? Is there a "
        "consistent cliff across models?]"
    )
    lines.append("")


def _section_cross_tr(lines: list[str], analysis: dict) -> None:
    """Section 23: Cross-TR validation."""
    lines.append("## 23. Cross-TR Validation")
    lines.append("")

    cross_tr = analysis.get("cross_tr_validation", {})
    if not cross_tr:
        lines.append("*No cross-TR data (TR134 baseline not available).*")
        lines.append("")
        return

    lines.append(
        "| Model | TR139 Direct Q8_0 Refusal | N | Note |"
    )
    lines.append(
        "|-------|---------------------------|---|------|"
    )
    for model, data in sorted(cross_tr.items()):
        lines.append(
            f"| {model} | "
            f"{_fmt_pct(data['tr139_direct_q8_refusal_rate'])} | "
            f"{data['n']} | {data.get('note', '')} |"
        )
    lines.append("")
    lines.append(
        "[HAND-WRITE: Compare with TR134 AdvBench refusal rates. "
        "Delta <5pp = consistent baselines.]"
    )
    lines.append("")


def _section_tost(lines: list[str], analysis: dict) -> None:
    """Section 24: TOST equivalence."""
    lines.append("## 24. TOST Equivalence Tests (+/- 3pp)")
    lines.append("")

    tost = analysis.get("tost_results", [])
    if not tost:
        lines.append("*No TOST data.*")
        lines.append("")
        return

    equiv = [t for t in tost if t.get("equivalent_at_3pp")]
    lines.append(
        f"**{len(equiv)}/{len(tost)} quant comparisons equivalent "
        f"to Q8_0 within +/-3pp.**"
    )
    lines.append("")

    lines.append("| Model | Strategy | Quant | p(TOST) | Equivalent |")
    lines.append("|-------|----------|-------|---------|------------|")
    for t in tost:
        eq = "Yes" if t["equivalent_at_3pp"] else "No"
        lines.append(
            f"| {t['model']} | {t['strategy']} | {t['quant']} | "
            f"{_fmt_pval(t['p_tost'])} | {eq} |"
        )
    lines.append("")


def _section_power(lines: list[str], analysis: dict) -> None:
    """Section 25: Power analysis."""
    lines.append("## 25. Power Analysis (MDE at 80%)")
    lines.append("")

    power = analysis.get("power_analysis", [])
    if not power:
        lines.append("*No power analysis data.*")
        lines.append("")
        return

    lines.append(
        "| Model | Strategy | N/quant | Baseline ASR | MDE (80%) |"
    )
    lines.append(
        "|-------|----------|---------|-------------|-----------|"
    )
    for p in power:
        lines.append(
            f"| {p['model']} | {p['strategy']} | {p['n_per_quant']} | "
            f"{_fmt_pct(p['baseline_asr'])} | {_fmt_pct(p['mde_80pct'])} |"
        )
    lines.append("")
    lines.append(
        "[HAND-WRITE: Can we detect the expected effect sizes? "
        "N=30 per cell gives MDE of ~X pp.]"
    )
    lines.append("")


def _section_persistence_curves(lines: list[str], analysis: dict) -> None:
    """Section 26: Phase 2 persistence curves."""
    lines.append("## 26. Phase 2 Persistence Curves")
    lines.append("")
    curves = analysis.get("phase2_persistence_curves", [])
    if not curves:
        lines.append("*No persistence curve data.*")
        lines.append("")
        return
    lines.append(
        "Turn-by-turn refusal rates under continued pressure. Each curve "
        "shows how refusal probability evolves across 5 pressure follow-ups "
        "after the initial harmful request."
    )
    lines.append("")
    for entry in curves:
        model = entry.get("model", "?")
        quant = entry.get("quant", "?")
        lines.append(f"### {model} @ {quant}")
        lines.append("")
        lines.append("| Turn | Mean Refusal | N Refused | N Total |")
        lines.append("|------|-------------|-----------|---------|")
        for pt in entry.get("persistence_curve", []):
            lines.append(
                f"| {pt['turn']} | {_fmt_pct(pt['mean_refusal_score'])} "
                f"| {pt['n_refused']} | {pt['n_total']} |"
            )
        lines.append("")
    lines.append(
        "[HAND-WRITE: Interpret the persistence curves. Do lower-quant "
        "models show steeper drops in refusal across pressure turns?]"
    )
    lines.append("")


def _section_variance_decomp(lines: list[str], analysis: dict) -> None:
    """Section 27: Variance decomposition."""
    lines.append("## 27. Variance Decomposition")
    lines.append("")
    vd = analysis.get("variance_decomposition", {})
    if not vd:
        lines.append("*No variance decomposition data.*")
        lines.append("")
        return
    lines.append(
        "How much of the total ASR variance is explained by each factor? "
        "This identifies whether quantization, strategy choice, or model "
        "identity drives the most variation in attack success."
    )
    lines.append("")
    lines.append("| Factor | % Variance Explained |")
    lines.append("|--------|---------------------|")
    lines.append(f"| Quantization | {vd.get('pct_quant', 0):.1f}% |")
    lines.append(f"| Attack Strategy | {vd.get('pct_strategy', 0):.1f}% |")
    lines.append(f"| Model | {vd.get('pct_model', 0):.1f}% |")
    lines.append(f"| Residual | {vd.get('pct_residual', 0):.1f}% |")
    lines.append("")
    lines.append(f"*N = {vd.get('n_total', 0)} observations.*")
    lines.append("")
    lines.append(
        "[HAND-WRITE: Which factor dominates? If strategy >> quant, "
        "multi-turn technique matters more than compression level.]"
    )
    lines.append("")


def _section_amplification(lines: list[str], analysis: dict) -> None:
    """Section 28: Amplification ratio."""
    lines.append("## 28. Multi-Turn Amplification Ratio")
    lines.append("")
    amp = analysis.get("amplification_ratio", {})
    table = amp.get("table", [])
    slopes = amp.get("slopes", [])
    if not table:
        lines.append("*No amplification ratio data.*")
        lines.append("")
        return
    lines.append(
        "Amplification ratio = multi-turn ASR / direct ASR. Values > 1.0 "
        "indicate the multi-turn strategy is more effective than a direct "
        "request. The key question: does quantization increase this ratio?"
    )
    lines.append("")
    lines.append(
        "| Model | Quant | Strategy | Direct ASR | Multi-Turn ASR | Amplification |"
    )
    lines.append(
        "|-------|-------|----------|-----------|----------------|---------------|"
    )
    for row in table:
        lines.append(
            f"| {row['model']} | {row['quant']} | {row['strategy']} "
            f"| {_fmt_pct(row['direct_asr'])} "
            f"| {_fmt_pct(row['multi_turn_asr'])} "
            f"| {row['amplification_ratio']} |"
        )
    lines.append("")
    if slopes:
        lines.append("### Amplification Slope vs BPW")
        lines.append("")
        lines.append(
            "Negative slope = amplification increases as quant level decreases."
        )
        lines.append("")
        lines.append("| Model | Strategy | Slope (amp/BPW) |")
        lines.append("|-------|----------|----------------|")
        for s in slopes:
            lines.append(
                f"| {s['model']} | {s['strategy']} "
                f"| {_fmt_signed(s['amp_slope_per_bpw'])} |"
            )
        lines.append("")
    lines.append(
        "[HAND-WRITE: Does quantization amplify multi-turn effectiveness "
        "disproportionately? This is the core novel finding of TR139.]"
    )
    lines.append("")


def _section_conditional_asr(lines: list[str], analysis: dict) -> None:
    """Section 29: Conditional ASR."""
    lines.append("## 29. Conditional ASR (Given Setup Compliance)")
    lines.append("")
    cond = analysis.get("conditional_asr", [])
    if not cond:
        lines.append("*No conditional ASR data.*")
        lines.append("")
        return
    lines.append(
        "Does compliance on benign setup turns predict compliance on the "
        "target harmful turn? Conditional ASR = P(target compliance | "
        "setup compliance). Uplift = conditional - unconditional ASR."
    )
    lines.append("")
    lines.append(
        "| Strategy | Model | Quant | Setup Compliance | Cond. ASR "
        "| Uncond. ASR | Uplift |"
    )
    lines.append(
        "|----------|-------|-------|-----------------|----------"
        "|-------------|--------|"
    )
    for row in cond:
        lines.append(
            f"| {row['strategy']} | {row['model']} | {row['quant']} "
            f"| {_fmt_pct(row['setup_compliance_rate'])} "
            f"| {_fmt_pct(row['conditional_asr'])} "
            f"| {_fmt_pct(row['unconditional_asr'])} "
            f"| {_fmt_signed(row['uplift'])} |"
        )
    lines.append("")
    lines.append(
        "[HAND-WRITE: High uplift means setup compliance is a strong "
        "predictor — the multi-turn conversation genuinely conditions "
        "the model toward compliance. This validates the attack mechanism.]"
    )
    lines.append("")


def _section_hypothesis_eval(lines: list[str], analysis: dict) -> None:
    """Section 30: Formal hypothesis evaluation."""
    lines.append("## 30. Hypothesis Evaluation")
    lines.append("")

    hyp = analysis.get("hypothesis_evaluation", {})
    if not hyp:
        lines.append("*No hypothesis evaluation data.*")
        lines.append("")
        return

    for h_key, h_data in sorted(hyp.items()):
        lines.append(f"### {h_key}")
        lines.append("")
        lines.append(f"**{h_data.get('summary', 'No data')}**")
        lines.append("")
        if "tests" in h_data:
            for t in h_data["tests"]:
                lines.append(f"- {t}")
        lines.append("")


def _section_limitations(lines: list[str], analysis: dict) -> None:
    """Section 31: Limitations."""
    lines.append("## 31. Limitations")
    lines.append("")
    lines.append(
        "1. **Small-to-medium models** (1.2-8B params). Larger models "
        "(13B+) may show different patterns; safety training is "
        "typically stronger in larger models."
    )
    lines.append(
        "2. **Regex classifier limitations.** RefusalDetector may miss "
        "nuanced compliance or over-count refusals. LLM judge "
        "partially mitigates but is not ground truth."
    )
    lines.append(
        "3. **Fixed attack templates.** Real multi-turn attacks are "
        "adaptive; our templates are fixed scripts. An adaptive "
        "attacker might achieve higher ASR."
    )
    lines.append(
        "4. **50 behaviors.** 5 per category provides moderate "
        "per-category power; some rare categories may still be "
        "underpowered for interaction effects."
    )
    lines.append(
        "5. **Single GPU (RTX 4080 Laptop).** Results may differ "
        "on other hardware due to floating-point determinism."
    )
    lines.append(
        "6. **Ollama quantization only (GGUF).** Other quantization "
        "methods (GPTQ, AWQ, bitsandbytes) may behave differently."
    )
    lines.append(
        "7. **temp=0 throughout.** Non-zero temperature could "
        "interact with both quantization and multi-turn strategies."
    )
    lines.append("")


def _section_conclusions(lines: list[str], analysis: dict) -> None:
    """Section 32: Conclusions."""
    lines.append("## 32. Conclusions")
    lines.append("")
    lines.append("[HAND-WRITE: Final conclusions addressing H1, H2, H3]")
    lines.append("")
    lines.append("### Key Findings")
    lines.append("")
    lines.append("1. [Finding about ASR x quant relationship]")
    lines.append("2. [Finding about multi-turn amplification vs direct]")
    lines.append("3. [Finding about persistence under pressure]")
    lines.append("4. [Finding about per-category vulnerability]")
    lines.append("5. [Finding about critical quant thresholds]")
    lines.append("")


def _section_production_guidance(lines: list[str], analysis: dict) -> None:
    """Section 29: Production guidance."""
    lines.append("## 33. Production Guidance")
    lines.append("")
    lines.append(
        "[HAND-WRITE: Actionable recommendations for deploying "
        "quantized models in multi-turn settings]"
    )
    lines.append("")
    lines.append("### Recommendations")
    lines.append("")
    lines.append(
        "1. **Quant floor for multi-turn safety:** [Specify based on "
        "critical threshold findings]"
    )
    lines.append(
        "2. **Per-turn safety monitoring:** Score every turn in "
        "multi-turn conversations, not just the final response"
    )
    lines.append(
        "3. **Strategy-aware guardrails:** [Which strategies are most "
        "dangerous at which quant levels?]"
    )
    lines.append(
        "4. **Persistence testing:** Include multi-turn pressure tests "
        "in safety evaluation suites, not just single-turn"
    )
    lines.append("")


def _section_reproducibility(lines: list[str], analysis: dict) -> None:
    """Section 30: Reproducibility."""
    lines.append("## 34. Reproducibility")
    lines.append("")
    git_hash = _get_git_hash()
    lines.append(f"- **Git commit:** `{git_hash}`")
    lines.append(f"- **Hardware:** NVIDIA RTX 4080 Laptop GPU (12GB VRAM)")
    lines.append(f"- **Backend:** Ollama (GGUF quantization)")
    lines.append(f"- **Temperature:** 0.0 (deterministic)")
    lines.append(f"- **Seed:** 42")
    lines.append(f"- **max_new_tokens:** 256")
    lines.append(
        f"- **Conversations:** {analysis.get('n_conversations', 0)}"
    )
    lines.append("")
    lines.append("```bash")
    lines.append("# Reproduce")
    lines.append("python research/tr139/run.py -v")
    lines.append("```")
    lines.append("")


def _section_appendix_asr(lines: list[str], analysis: dict) -> None:
    """Appendix A: Full ASR matrix."""
    lines.append("## Appendix A: Full ASR Matrix")
    lines.append("")

    asr_table = analysis.get("phase1_asr_matrix", [])
    if not asr_table:
        lines.append("*No data.*")
        lines.append("")
        return

    lines.append(
        "| Model | Quant | BPW | Strategy | ASR | N | k | CI_lo | CI_hi |"
    )
    lines.append(
        "|-------|-------|-----|----------|-----|---|---|-------|-------|"
    )
    for row in asr_table:
        lines.append(
            f"| {row['model']} | {row['quant']} | {row['bpw']} | "
            f"{row['strategy']} | {_fmt_pct(row['asr'])} | "
            f"{row['n']} | {row['k']} | {row['ci_lo']:.4f} | "
            f"{row['ci_hi']:.4f} |"
        )
    lines.append("")


def _section_appendix_stats(lines: list[str], analysis: dict) -> None:
    """Appendix B: Statistical test tables."""
    lines.append("## Appendix B: Statistical Test Tables")
    lines.append("")
    lines.append("See Section 15 for full Fisher/Chi-sq/Holm tables.")
    lines.append("")

    pairwise = analysis.get("phase1_pairwise", [])
    if pairwise:
        lines.append("### Pairwise Quant Comparisons (Welch t, Cohen's d)")
        lines.append("")
        lines.append(
            "| Model | Strategy | Q_A | Q_B | Mean_A | Mean_B | "
            "t | p | d | p_Holm |"
        )
        lines.append(
            "|-------|----------|-----|-----|--------|--------|"
            "---|---|---|--------|"
        )
        for pw in pairwise:
            lines.append(
                f"| {pw['model']} | {pw['strategy']} | "
                f"{pw['quant_a']} | {pw['quant_b']} | "
                f"{pw['mean_a']:.3f} | {pw['mean_b']:.3f} | "
                f"{pw['t']:.3f} | {_fmt_pval(pw['p'])} | "
                f"{pw['cohens_d']:.3f} | {_fmt_pval(pw.get('p_holm', 1))} |"
            )
        lines.append("")


def _section_appendix_glossary(lines: list[str], analysis: dict) -> None:
    """Appendix C: Glossary."""
    lines.append("## Appendix C: Glossary")
    lines.append("")
    terms = [
        ("ASR", "Attack Success Rate: fraction of conversations where the target turn elicited compliance"),
        ("BPW", "Bits Per Weight: effective precision of quantized weights"),
        ("TOFC", "Turn of First Compliance: earliest turn where model provided harmful content"),
        ("Persistence Score", "Fraction of turns where model maintained refusal (1.0 = perfect resistance)"),
        ("Pressure Resistance", "Fraction of pressure follow-up turns where model maintained refusal"),
        ("Wilson CI", "Wilson score confidence interval for binomial proportions"),
        ("TOST", "Two One-Sided Tests for equivalence within +/-3pp bounds"),
        ("MDE", "Minimum Detectable Effect at 80% statistical power"),
        ("Cohen's d", "Standardized effect size (pooled SD denominator)"),
        ("Holm correction", "Holm-Bonferroni correction for multiple comparisons"),
        ("GGUF", "GPT-Generated Unified Format: quantization format used by llama.cpp/Ollama"),
    ]
    for term, defn in terms:
        lines.append(f"- **{term}:** {defn}")
    lines.append("")


def _section_references(lines: list[str], analysis: dict) -> None:
    """Appendix D: References."""
    lines.append("## Appendix D: References")
    lines.append("")
    refs = [
        "Foot-in-the-Door (EMNLP 2025): https://aclanthology.org/2025.emnlp-main.100.pdf",
        "Multi-Turn Jailbreaks Simpler Than They Seem (May 2025): https://arxiv.org/html/2508.07646v1",
        "Multi-Turn Attention Shifting (AAAI 2025): https://ojs.aaai.org/index.php/AAAI/article/view/34553/36708",
        "Crescendo: Escalation-Based Jailbreak (Microsoft, 2024)",
        "HarmLevelBench (Nov 2024): https://arxiv.org/abs/2411.06835",
        "Q-resafe (ICML 2025): https://openreview.net/forum?id=VarjSNbij7",
        "Alignment-Aware Quantization (Nov 2025): https://arxiv.org/abs/2511.07842",
        "JailbreakBench (NeurIPS 2024): https://jailbreakbench.github.io/",
        "AdvBench (Zou et al., 2023): https://github.com/llm-attacks/llm-attacks",
    ]
    for ref in refs:
        lines.append(f"- {ref}")
    lines.append("")


# ── Report generation ─────────────────────────────────────────────


def _generate_report(run_dir: Path) -> str:
    """Generate full markdown report from analysis JSON."""
    analysis_path = run_dir / "tr139_analysis.json"
    if not analysis_path.exists():
        logger.error("tr139_analysis.json not found in %s", run_dir)
        return ""

    with open(analysis_path, encoding="utf-8") as f:
        analysis = json.load(f)

    lines: list[str] = []

    _section_metadata(lines, analysis)
    _section_abstract(lines, analysis)
    _section_toc(lines, analysis)
    _section_executive_summary(lines, analysis)
    _section_hypotheses(lines, analysis)
    _section_methodology(lines, analysis)
    _section_models(lines, analysis)
    _section_attack_strategies(lines, analysis)
    _section_phase1_asr(lines, analysis)
    _section_tofc(lines, analysis)
    _section_asr_slopes(lines, analysis)
    _section_strategy_ranking(lines, analysis)
    _section_per_category(lines, analysis)
    _section_model_anova(lines, analysis)
    _section_two_way_anova(lines, analysis)
    _section_stat_tests(lines, analysis)
    _section_phase2_persistence(lines, analysis)
    _section_persistence_slopes(lines, analysis)
    _section_trajectories(lines, analysis)
    _section_cross_strategy(lines, analysis)
    _section_judge_agreement(lines, analysis)
    _section_latency(lines, analysis)
    _section_critical_thresholds(lines, analysis)
    _section_cross_tr(lines, analysis)
    _section_tost(lines, analysis)
    _section_power(lines, analysis)
    _section_persistence_curves(lines, analysis)
    _section_variance_decomp(lines, analysis)
    _section_amplification(lines, analysis)
    _section_conditional_asr(lines, analysis)
    _section_hypothesis_eval(lines, analysis)
    _section_limitations(lines, analysis)
    _section_conclusions(lines, analysis)
    _section_production_guidance(lines, analysis)
    _section_reproducibility(lines, analysis)
    _section_appendix_asr(lines, analysis)
    _section_appendix_stats(lines, analysis)
    _section_appendix_glossary(lines, analysis)
    _section_references(lines, analysis)

    return "\n".join(lines)


# ── CLI ──────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description="TR139: Generate multi-turn jailbreak report",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--run-dir", type=str, default=None)
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    output_base = _REPO / "research" / "tr139" / "results"
    if args.run_dir:
        run_dir = Path(args.run_dir)
    else:
        run_dir = find_latest_run(output_base)

    if run_dir is None or not run_dir.exists():
        logger.error("No run directory found in %s", output_base)
        return 1

    report_text = _generate_report(run_dir)
    if not report_text:
        return 1

    report_path = run_dir / "tr139_report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_text)

    n_lines = len(report_text.splitlines())
    logger.info("Report written to %s (%d lines)", report_path, n_lines)
    print(f"Report generated: {report_path} ({n_lines} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
