"""TR135: Generate concurrency x safety report.

Reads tr135_analysis.json and generates a markdown report.

Sections:
  1. Executive Summary
  2. Experimental Design
  3. Per-Task Safety Slopes with Bootstrap CIs
  4. Aggregate Safety vs Concurrency
  5. Capability vs Concurrency (control arm)
  6. Safety-Capability Divergence
  7. Latency vs Concurrency
  8. Per-Task Breakdown
  9. Pairwise Statistical Tests (Holm, Cohen's d, TOST equivalence)
  10. LLM Judge Agreement by N
  11. Baseline (N=1) Reference
  12. Normalized Degradation Curves
  13. Agent Disagreement Analysis
  14. Disagreement-Safety Correlation (Pearson r)
  15. Per-Task Slope Heterogeneity
  16. Power Analysis
  17. Cross-Experiment Validation (vs TR134 Phase 3)
  18. Jailbreak Amplification vs Concurrency (with amplification ratios)
  19. Methodology & Limitations

Usage:
    python research/tr135/generate_report.py [-v] [--run-dir PATH]
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

from research.tr135.shared.utils import find_latest_run

logger = logging.getLogger("tr135.generate_report")


def _w(lines: list[str], text: str = "") -> None:
    lines.append(text)


def _section_header(lines: list[str], analysis: dict) -> None:
    meta = analysis.get("metadata", {})
    _w(lines, "# TR135: Multi-Agent Concurrency x Safety")
    _w(lines)
    _w(lines, f"**Generated:** {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}")
    _w(lines, f"**Raw records:** {meta.get('total_raw_records', 0):,}")
    _w(lines, f"**Prompt-level observations:** {meta.get('total_prompt_level', 0):,}")
    _w(lines, f"**Models:** {', '.join(meta.get('models', []))}")
    _w(lines, f"**Concurrency levels:** {meta.get('n_levels', [])}")
    _w(lines)
    note = meta.get("statistical_note", "")
    if note:
        _w(lines, f"> **Statistical note:** {note}")
        _w(lines)


def _section_executive_summary(lines: list[str], analysis: dict) -> None:
    _w(lines, "## 1. Executive Summary")
    _w(lines)
    _w(lines, "This experiment tests whether N-agent concurrency degrades model safety")
    _w(lines, "beyond what general capability degradation alone would predict.")
    _w(lines)

    div = analysis.get("safety_capability_divergence", {})
    finding_num = 1
    for model, data in sorted(div.items()):
        interp = data.get("interpretation", "unknown").replace("_", " ")
        s_slope = data.get("safety_slope", 0)
        c_slope = data.get("capability_slope", 0)
        diff = data.get("slope_difference", 0)
        _w(lines, f"{finding_num}. **{model}**: {interp} "
           f"(safety slope={s_slope:+.4f}/N, capability slope={c_slope:+.4f}/N, "
           f"diff={diff:+.4f})")
        finding_num += 1
    _w(lines)


def _section_design(lines: list[str], analysis: dict) -> None:
    _w(lines, "## 2. Experimental Design")
    _w(lines)
    _w(lines, "| Parameter | Value |")
    _w(lines, "|-----------|-------|")
    meta = analysis.get("metadata", {})
    _w(lines, f"| Models | {', '.join(meta.get('models', []))} |")
    _w(lines, f"| N levels | {meta.get('n_levels', [])} |")
    _w(lines, f"| Raw records | {meta.get('total_raw_records', 0):,} |")
    _w(lines, f"| Prompt-level observations | {meta.get('total_prompt_level', 0):,} |")
    _w(lines, "| Safety tasks | AdvBench, TruthfulQA, BBQ, Jailbreak |")
    _w(lines, "| Capability control | MMLU (50 questions) |")
    _w(lines, "| Quantization | Q4_K_M (deployment-realistic) |")
    _w(lines, "| Backend | Single Ollama instance |")
    _w(lines, "| Aggregation | Per-prompt mean across agents, then group stats |")
    _w(lines)


def _section_per_task_slopes(lines: list[str], analysis: dict) -> None:
    _w(lines, "## 3. Per-Task Safety Slopes with Bootstrap CIs")
    _w(lines)
    _w(lines, "Slope of safety score vs N (per agent added). 95% CI from 2000-iteration bootstrap.")
    _w(lines)
    slopes = analysis.get("safety_slopes", {})
    for model, model_slopes in sorted(slopes.items()):
        _w(lines, f"### {model}")
        _w(lines)
        _w(lines, "| Task | Slope/N | 95% CI | R² | N Levels |")
        _w(lines, "|------|---------|--------|-----|----------|")
        for task, data in sorted(model_slopes.items()):
            if task == "_aggregate_safety":
                continue
            ci_str = f"[{data['ci_95_lo']:.6f}, {data['ci_95_hi']:.6f}]"
            ns_str = str(data.get("n_levels", []))
            _w(lines, f"| {task} | {data['slope']:+.6f} | {ci_str} | "
               f"{data['r_squared']:.4f} | {ns_str} |")
        _w(lines)

        # Per-task N-level means
        for task, data in sorted(model_slopes.items()):
            if task == "_aggregate_safety" or not data.get("n_levels"):
                continue
            _w(lines, f"**{task}** means:")
            _w(lines)
            _w(lines, "| N | Mean Score | Prompts |")
            _w(lines, "|---|-----------|---------|")
            n_per = data.get("n_prompts_per_level", [])
            for i, (n, m) in enumerate(zip(data["n_levels"], data["means"])):
                np_str = str(n_per[i]) if i < len(n_per) else "?"
                _w(lines, f"| {n} | {m:.4f} | {np_str} |")
            _w(lines)


def _section_aggregate_safety(lines: list[str], analysis: dict) -> None:
    _w(lines, "## 4. Aggregate Safety vs Concurrency")
    _w(lines)
    slopes = analysis.get("safety_slopes", {})
    for model, model_slopes in sorted(slopes.items()):
        agg = model_slopes.get("_aggregate_safety", {})
        if not agg:
            continue
        _w(lines, f"### {model}")
        _w(lines)
        ci_str = f"[{agg.get('ci_95_lo', 0):.6f}, {agg.get('ci_95_hi', 0):.6f}]"
        _w(lines, f"Slope: **{agg['slope']:+.6f}** per agent "
           f"(R²={agg['r_squared']:.4f}, 95% CI: {ci_str})")
        _w(lines)
        if agg.get("n_levels") and agg.get("means"):
            _w(lines, "| N | Mean Safety Score |")
            _w(lines, "|---|------------------|")
            for n, m in zip(agg["n_levels"], agg["means"]):
                _w(lines, f"| {n} | {m:.4f} |")
            _w(lines)


def _section_capability(lines: list[str], analysis: dict) -> None:
    _w(lines, "## 5. Capability vs Concurrency (Control Arm)")
    _w(lines)
    _w(lines, "MMLU accuracy as a function of N. If capability degrades at the same rate")
    _w(lines, "as safety, then concurrency hurts everything — not safety specifically.")
    _w(lines)
    cap = analysis.get("capability_slopes", {})
    for model, data in sorted(cap.items()):
        _w(lines, f"### {model}")
        _w(lines)
        ci_str = f"[{data.get('ci_95_lo', 0):.6f}, {data.get('ci_95_hi', 0):.6f}]"
        _w(lines, f"Slope: **{data['slope']:+.6f}** per agent "
           f"(R²={data['r_squared']:.4f}, 95% CI: {ci_str})")
        _w(lines)
        if data.get("n_levels") and data.get("means"):
            _w(lines, "| N | Mean MMLU Accuracy |")
            _w(lines, "|---|-------------------|")
            for n, m in zip(data["n_levels"], data["means"]):
                _w(lines, f"| {n} | {m:.4f} |")
            _w(lines)


def _section_divergence(lines: list[str], analysis: dict) -> None:
    _w(lines, "## 6. Safety-Capability Divergence")
    _w(lines)
    _w(lines, "**Key research question:** Does safety degrade faster than capability under concurrency?")
    _w(lines)
    _w(lines, "| Model | Safety Slope | Safety CI | Cap Slope | Cap CI | Diff | Interpretation |")
    _w(lines, "|-------|-------------|-----------|-----------|--------|------|----------------|")
    div = analysis.get("safety_capability_divergence", {})
    for model, data in sorted(div.items()):
        s_ci = data.get("safety_ci", [0, 0])
        c_ci = data.get("capability_ci", [0, 0])
        interp = data.get("interpretation", "unknown").replace("_", " ")
        _w(lines, f"| {model} | {data['safety_slope']:+.6f} | "
           f"[{s_ci[0]:.6f}, {s_ci[1]:.6f}] | "
           f"{data['capability_slope']:+.6f} | "
           f"[{c_ci[0]:.6f}, {c_ci[1]:.6f}] | "
           f"{data['slope_difference']:+.6f} | {interp} |")
    _w(lines)


def _section_latency_vs_n(lines: list[str], analysis: dict) -> None:
    _w(lines, "## 7. Latency vs Concurrency")
    _w(lines)
    slopes = analysis.get("latency_slopes", {})
    for model, data in sorted(slopes.items()):
        _w(lines, f"### {model}")
        _w(lines)
        _w(lines, f"Slope: **{data['slope_ms_per_n']:.1f}** ms/agent (R²={data['r_squared']:.4f})")
        _w(lines)
        _w(lines, "| N | Mean Latency (ms) |")
        _w(lines, "|---|-------------------|")
        for n, m in zip(data["n_levels"], data["mean_latencies_ms"]):
            _w(lines, f"| {n} | {m:.1f} |")
        _w(lines)


def _section_per_task(lines: list[str], analysis: dict) -> None:
    _w(lines, "## 8. Per-Task Breakdown")
    _w(lines)
    stats = analysis.get("group_stats", {})
    _w(lines, "| Model | N | Task | Score | Score CI | Latency (ms) | Prompts | Raw Records |")
    _w(lines, "|-------|---|------|-------|---------|-------------|---------|-------------|")
    for key in sorted(stats.keys()):
        s = stats[key]
        score_str = f"{s['score_mean']:.4f}" if s.get("score_mean") is not None else "---"
        ci_str = (f"[{s['score_ci_lo']:.4f}, {s['score_ci_hi']:.4f}]"
                  if s.get("score_ci_lo") is not None else "---")
        lat_str = f"{s['latency_mean_ms']:.0f}" if s.get("latency_mean_ms") is not None else "---"
        _w(lines, f"| {s['model']} | {s['n_agents']} | {s['task']} | {score_str} | "
           f"{ci_str} | {lat_str} | {s.get('n_prompts', '?')} | {s.get('n_raw_records', '?')} |")
    _w(lines)


def _section_pairwise(lines: list[str], analysis: dict) -> None:
    _w(lines, "## 9. Pairwise Statistical Tests")
    _w(lines)
    _w(lines, "Paired t-test between adjacent N levels on prompt-level safety scores.")
    _w(lines, "Same prompts appear at every N level, enabling paired comparison.")
    _w(lines, "Significance corrected via Holm-Bonferroni. Effect size via Cohen's d.")
    _w(lines)
    pw = analysis.get("pairwise_tests", {})
    for model, pairs in sorted(pw.items()):
        _w(lines, f"### {model}")
        _w(lines)
        if not pairs:
            _w(lines, "No pairs with sufficient samples.")
            _w(lines)
            continue
        _w(lines, "| N_a -> N_b | Mean_a | Mean_b | Diff | t | p | Cohen's d | Holm Sig | TOST Equiv | Paired |")
        _w(lines, "|------------|--------|--------|------|---|---|-----------|----------|------------|--------|")
        for p in pairs:
            holm = "Yes" if p.get("significant_holm") else "No"
            tost = "Yes" if p.get("tost_equivalent") else "No"
            _w(lines, f"| {p['n_a']} -> {p['n_b']} | {p['mean_a']:.4f} | {p['mean_b']:.4f} | "
               f"{p['diff']:+.4f} | {p['t_stat']:.2f} | {p['p_value']:.4f} | "
               f"{p['cohens_d']:+.4f} | {holm} | {tost} | "
               f"{p.get('n_paired_prompts', '?')} |")
        _w(lines)
        _w(lines, f"*TOST equivalence margin: ±{pairs[0].get('tost_margin', 0.03) * 100:.0f}pp. "
           f"'Yes' = effect is within ±margin (confirmed equivalent). "
           f"'No' = cannot confirm equivalence (may be underpowered).*")
        _w(lines)


def _section_judge(lines: list[str], analysis: dict) -> None:
    _w(lines, "## 10. LLM Judge Agreement by N")
    _w(lines)
    ja = analysis.get("judge_agreement", {})
    if not ja:
        _w(lines, "*No judge data available.*")
        _w(lines)
        return
    _w(lines, "Cohen's kappa between regex classifiers and LLM judge (refusal tasks):")
    _w(lines)
    _w(lines, "| N | Kappa | Pairs | Agreement % |")
    _w(lines, "|---|-------|-------|-------------|")
    for key in sorted(ja.keys()):
        d = ja[key]
        _w(lines, f"| {key} | {d['kappa']:.4f} | {d['n_pairs']} | {d['agreement_pct']:.1f}% |")
    _w(lines)


def _section_baseline(lines: list[str], analysis: dict) -> None:
    _w(lines, "## 11. Baseline (N=1) Reference")
    _w(lines)
    stats = analysis.get("group_stats", {})
    _w(lines, "| Model | Task | N=1 Score | N=1 Latency (ms) | Prompts |")
    _w(lines, "|-------|------|-----------|-------------------|---------|")
    for key in sorted(stats.keys()):
        s = stats[key]
        if s["n_agents"] == 1:
            score_str = f"{s['score_mean']:.4f}" if s.get("score_mean") is not None else "---"
            lat_str = f"{s['latency_mean_ms']:.0f}" if s.get("latency_mean_ms") is not None else "---"
            _w(lines, f"| {s['model']} | {s['task']} | {score_str} | {lat_str} | {s.get('n_prompts', '?')} |")
    _w(lines)


def _section_normalized(lines: list[str], analysis: dict) -> None:
    _w(lines, "## 12. Normalized Degradation Curves")
    _w(lines)
    _w(lines, "Values relative to N=1 baseline (1.0 = no change):")
    _w(lines)
    norm = analysis.get("normalized", {})
    stats = analysis.get("group_stats", {})
    _w(lines, "| Model | N | Task | Norm Score | Norm Latency |")
    _w(lines, "|-------|---|------|-----------|-------------|")
    for key in sorted(norm.keys()):
        n = norm[key]
        s = stats.get(key, {})
        ns = f"{n['norm_score']:.4f}" if n.get("norm_score") is not None else "---"
        nl = f"{n['norm_latency']:.4f}" if n.get("norm_latency") is not None else "---"
        _w(lines, f"| {s.get('model', '?')} | {s.get('n_agents', '?')} | {s.get('task', '?')} | {ns} | {nl} |")
    _w(lines)


def _section_agent_disagreement(lines: list[str], analysis: dict) -> None:
    _w(lines, "## 13. Agent Disagreement Analysis")
    _w(lines)
    _w(lines, "Mean std-dev of scores across agents for the same prompt (higher = more disagreement):")
    _w(lines)
    stats = analysis.get("group_stats", {})
    has_data = any(s.get("mean_agent_disagreement", 0) > 0 for s in stats.values())
    if not has_data:
        _w(lines, "*N=1 has no disagreement by definition. Higher N levels may show within-prompt variance.*")
        _w(lines)
        return
    _w(lines, "| Model | N | Task | Mean Agent Disagreement |")
    _w(lines, "|-------|---|------|------------------------|")
    for key in sorted(stats.keys()):
        s = stats[key]
        if s["n_agents"] > 1 and s.get("mean_agent_disagreement", 0) > 0:
            _w(lines, f"| {s['model']} | {s['n_agents']} | {s['task']} | "
               f"{s['mean_agent_disagreement']:.4f} |")
    _w(lines)


def _section_disagreement_corr(lines: list[str], analysis: dict) -> None:
    _w(lines, "## 14. Disagreement-Safety Correlation")
    _w(lines)
    _w(lines, "Does higher agent disagreement (within-prompt score variance) predict")
    _w(lines, "lower safety? If r < 0 and significant, concurrency creates unreliable safety.")
    _w(lines)
    dc = analysis.get("disagreement_correlation", {})
    if not dc:
        _w(lines, "*No disagreement correlation data (requires N > 1 data).*")
        _w(lines)
        return
    _w(lines, "| Model | Pearson r | t | p | N | Significant? | Interpretation |")
    _w(lines, "|-------|-----------|---|---|---|-------------|----------------|")
    for model, data in sorted(dc.items()):
        sig = "**Yes**" if data["significant"] else "No"
        _w(lines, f"| {model} | {data['pearson_r']:+.4f} | {data['t_stat']:.2f} | "
           f"{data['p_value']:.4f} | {data['n_observations']} | {sig} | "
           f"{data['interpretation']} |")
    _w(lines)


def _section_slope_heterogeneity(lines: list[str], analysis: dict) -> None:
    _w(lines, "## 15. Per-Task Slope Heterogeneity")
    _w(lines)
    _w(lines, "Do all safety tasks degrade at the same rate under concurrency?")
    _w(lines)
    sh = analysis.get("slope_heterogeneity", {})
    if not sh:
        _w(lines, "*Insufficient tasks for comparison.*")
        _w(lines)
        return
    for model, data in sorted(sh.items()):
        _w(lines, f"### {model}")
        _w(lines)
        _w(lines, "| Task | Slope/N |")
        _w(lines, "|------|---------|")
        for task, slope in sorted(data["task_slopes"].items()):
            _w(lines, f"| {task} | {slope:+.6f} |")
        _w(lines)
        _w(lines, f"- **Slope range:** {data['slope_range']:.6f}")
        _w(lines, f"- **Most affected:** {data['most_affected_task']}")
        _w(lines, f"- **Least affected:** {data['least_affected_task']}")
        _w(lines)


def _section_power(lines: list[str], analysis: dict) -> None:
    _w(lines, "## 16. Power Analysis")
    _w(lines)
    _w(lines, "Minimum detectable effect (MDE) at alpha=0.05, power=0.80.")
    _w(lines, "Effects smaller than the MDE may exist but cannot be reliably detected.")
    _w(lines)
    pa = analysis.get("power_analysis", {})
    if not pa:
        _w(lines, "*No power analysis data.*")
        _w(lines)
        return
    _w(lines, "| Model | Safety N | Safety MDE (pp) | Capability N | Cap MDE (Cohen's d) |")
    _w(lines, "|-------|----------|----------------|--------------|---------------------|")
    for model, data in sorted(pa.items()):
        mde_s = f"{data['mde_safety_pp']}" if data.get("mde_safety_pp") is not None else "---"
        mde_c = f"{data['mde_cohens_d']}" if data.get("mde_cohens_d") is not None else "---"
        _w(lines, f"| {model} | {data['n_safety_prompts']} | {mde_s} | "
           f"{data['n_capability_prompts']} | {mde_c} |")
    _w(lines)

    # Per-task MDE
    for model, data in sorted(pa.items()):
        per_task = data.get("per_task", {})
        if per_task:
            _w(lines, f"### {model} — Per-Task MDE")
            _w(lines)
            _w(lines, "| Task | N | Baseline Rate | MDE (pp) |")
            _w(lines, "|------|---|---------------|----------|")
            for task, td in sorted(per_task.items()):
                _w(lines, f"| {task} | {td['n']} | {td['baseline_rate']:.4f} | {td['mde_pp']} |")
            _w(lines)

    _w(lines, "**Interpretation:** If a pairwise test shows p > 0.05 (not significant) AND "
       "TOST shows 'No' (not equivalent), the result is **inconclusive** — the sample "
       "size may be too small to detect a real effect. Only when TOST confirms equivalence "
       "can we conclude safety is maintained.")
    _w(lines)


def _section_cross_validation(lines: list[str], analysis: dict) -> None:
    _w(lines, "## 17. Cross-Experiment Validation (vs TR134 Phase 3)")
    _w(lines)
    _w(lines, "Compares TR135 N=1 baseline scores to TR134 Phase 3 Q4_K_M scores.")
    _w(lines, "Same models, same quantization, same tasks — scores should agree within 5pp.")
    _w(lines)
    cv = analysis.get("cross_validation", {})
    if not cv:
        _w(lines, "*No TR134 Phase 3 results found for cross-validation.*")
        _w(lines)
        return
    for model, data in sorted(cv.items()):
        _w(lines, f"### {model}")
        _w(lines)
        _w(lines, "| Task | TR135 (N=1) | TR134 (Q4_K_M) | Diff (pp) | Consistent? |")
        _w(lines, "|------|------------|----------------|-----------|-------------|")
        for task, td in sorted(data.get("tasks", {}).items()):
            ok = "Yes" if td["consistent"] else "**No**"
            _w(lines, f"| {task} | {td['tr135_score']:.4f} | {td['tr134_score']:.4f} | "
               f"{td['diff_pp']:+.1f} | {ok} |")
        n_c = data["n_consistent"]
        n_t = data["n_tasks_compared"]
        _w(lines)
        _w(lines, f"**{n_c}/{n_t} tasks consistent** (< {data['tasks'][list(data['tasks'].keys())[0]]['threshold_pp']}pp threshold)")
        _w(lines)


def _section_jailbreak(lines: list[str], analysis: dict) -> None:
    _w(lines, "## 18. Jailbreak Amplification vs Concurrency")
    _w(lines)
    _w(lines, "Does concurrency amplify jailbreak success? Compliance rate (1 - refusal)")
    _w(lines, "broken down by jailbreak technique and N.")
    _w(lines)
    jb = analysis.get("jailbreak_breakdown", {})
    if not jb:
        _w(lines, "*No jailbreak data available.*")
        _w(lines)
        return
    for model, model_jb in sorted(jb.items()):
        _w(lines, f"### {model}")
        _w(lines)
        _w(lines, "| Jailbreak Type | Compliance Slope/N | N=1 Compliance | N=8 Compliance |")
        _w(lines, "|----------------|-------------------|----------------|----------------|")
        for jb_type, data in sorted(model_jb.items()):
            c_means = data["compliance_means"]
            c1 = f"{c_means[0]:.4f}" if c_means else "---"
            c8 = f"{c_means[-1]:.4f}" if c_means else "---"
            _w(lines, f"| {jb_type} | {data['compliance_slope_per_n']:+.6f} | {c1} | {c8} |")
        _w(lines)


def _section_methodology(lines: list[str]) -> None:
    _w(lines, "## 19. Methodology & Limitations")
    _w(lines)
    _w(lines, "### Design")
    _w(lines, "- Single Ollama instance shared by N concurrent agents (closed-loop)")
    _w(lines, "- Each agent processes all prompts independently (not load-balanced)")
    _w(lines, "- N-level ordering randomized per model to avoid thermal/cache confounds")
    _w(lines, "- Prompt ordering shuffled per agent to avoid sequence effects")
    _w(lines, "- **Per-prompt aggregation**: scores averaged across agents per (model, N, task, sample_id) before computing group statistics — avoids treating correlated within-prompt observations as independent")
    _w(lines, "- Safety classifiers: regex-based (RefusalDetector, TruthfulnessScorer, BiasDetector)")
    _w(lines, "- LLM judge: Qwen 2.5 7B Q8_0 (different family from evaluated models)")
    _w(lines)
    _w(lines, "### Statistical Methods")
    _w(lines, "- OLS regression for slope estimation (safety/capability/latency vs N)")
    _w(lines, "- 2000-iteration bootstrap for 95% CIs on slopes (resamples within N-level groups from prompt-level data)")
    _w(lines, "- Paired t-test for pairwise N-level comparisons (same prompts at every N)")
    _w(lines, "- TOST equivalence testing at ±3pp margin (confirms equivalence, not just failure to reject)")
    _w(lines, "- Holm-Bonferroni step-down correction for multiple comparisons")
    _w(lines, "- Cohen's d (pooled SD) for effect sizes")
    _w(lines, "- Cohen's kappa for inter-rater agreement (regex classifier vs LLM judge)")
    _w(lines, "- Power analysis: binary MDE via two-proportion z-test, continuous MDE via Cohen's d")
    _w(lines, "- P-values via regularized incomplete beta function (exact t-distribution, not normal approximation)")
    _w(lines)
    _w(lines, "### Limitations")
    _w(lines, "1. Single Ollama instance — not representative of distributed/load-balanced deployments")
    _w(lines, "2. Closed-loop pattern — actual concurrent depth may be < N due to serialization on single GPU")
    _w(lines, "3. Only two models tested (one 1.2B weak, one 7.6B strong) — limited generalizability")
    _w(lines, "4. Fixed quantization (Q4_K_M) — concurrency × quant-level interaction untested")
    _w(lines, "5. temperature=0.0 — no sampling variance; stochastic degradation untested")
    _w(lines, "6. MMLU capability control uses only 50 questions — wide CIs on capability slope")
    _w(lines, "7. Regex classifiers are surface-level — may miss nuanced safety failures")
    _w(lines, "8. No multi-turn evaluation — adversarial multi-turn attacks under concurrency untested")
    _w(lines, "9. Ollama may not be fully deterministic at temp=0 — minor run-to-run variance possible")
    _w(lines, "10. Single run per configuration — no multi-run variance estimation")
    _w(lines)


def generate_report(analysis: dict, run_dir: Path) -> str:
    """Generate the full markdown report."""
    lines: list[str] = []

    _section_header(lines, analysis)
    _section_executive_summary(lines, analysis)
    _section_design(lines, analysis)
    _section_per_task_slopes(lines, analysis)
    _section_aggregate_safety(lines, analysis)
    _section_capability(lines, analysis)
    _section_divergence(lines, analysis)
    _section_latency_vs_n(lines, analysis)
    _section_per_task(lines, analysis)
    _section_pairwise(lines, analysis)
    _section_judge(lines, analysis)
    _section_baseline(lines, analysis)
    _section_normalized(lines, analysis)
    _section_agent_disagreement(lines, analysis)
    _section_disagreement_corr(lines, analysis)
    _section_slope_heterogeneity(lines, analysis)
    _section_power(lines, analysis)
    _section_cross_validation(lines, analysis)
    _section_jailbreak(lines, analysis)
    _section_methodology(lines)

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="TR135 report generation")
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
        run_dir = find_latest_run("research/tr135/results")

    if not run_dir or not run_dir.exists():
        logger.error("No run directory found")
        return 1

    analysis_path = run_dir / "tr135_analysis.json"
    if not analysis_path.exists():
        logger.error("No analysis file found: %s", analysis_path)
        return 1

    with open(analysis_path, encoding="utf-8") as f:
        analysis = json.load(f)

    report = generate_report(analysis, run_dir)
    report_path = run_dir / "tr135_report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)

    logger.info("Report written to %s (%d lines)", report_path, len(report.splitlines()))
    print(f"\nReport: {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
