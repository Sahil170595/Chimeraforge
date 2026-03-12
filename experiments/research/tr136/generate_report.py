"""TR136: Generate cross-backend safety consistency report.

Reads tr136_analysis.json and generates a markdown report.

Sections:
  1. Executive Summary
  2. Experimental Design
  3. Per-Backend Safety Scores
  4. Per-Task Breakdown
  5. Pairwise Backend Agreement (binary)
  6. Response Divergence (Jaccard)
  7. Quantization vs Backend Effect
  8. Statistical Tests (Chi-Squared, all backends)
  9. LLM Judge Agreement per Backend
  10. Latency Comparison
  11. Error Analysis
  12. Pairwise Backend Comparisons (t-tests, Holm-corrected)
  13. Per-Task Backend Independence (chi-squared per task)
  14. Safety-Divergence Correlation
  15. Power Analysis
  16. Cross-Experiment Validation (vs TR134 Phase 3)
  17. Methodology & Limitations

Usage:
    python research/tr136/generate_report.py [-v] [--run-dir PATH]
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

from research.tr136.shared.utils import find_latest_run

logger = logging.getLogger("tr136.generate_report")


def _w(lines: list[str], text: str = "") -> None:
    lines.append(text)


def _section_header(lines: list[str], analysis: dict) -> None:
    meta = analysis.get("metadata", {})
    _w(lines, "# TR136: Cross-Backend Safety Consistency")
    _w(lines)
    _w(lines, f"**Generated:** {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}")
    _w(lines, f"**Total samples:** {meta.get('total_records', 0):,}")
    _w(lines, f"**Models:** {', '.join(meta.get('models', []))}")
    _w(lines, f"**Backends:** {', '.join(meta.get('backends', []))}")
    _w(lines)


def _section_executive_summary(lines: list[str], analysis: dict) -> None:
    _w(lines, "## 1. Executive Summary")
    _w(lines)
    _w(lines, "This experiment tests whether model safety behavior changes across")
    _w(lines, "serving backends (Ollama Q4_K_M, Ollama Q8_0, vLLM FP16, TGI FP16).")
    _w(lines)

    finding = 1
    qb = analysis.get("quant_vs_backend", {})
    for model, data in sorted(qb.items()):
        interp = data.get("interpretation", "unknown")
        qe = data.get("quant_effect_q8_minus_q4")
        be = data.get("backend_effect_vllm_minus_q8")
        _w(lines, f"{finding}. **{model}**: {interp.replace('_', ' ')}"
           f" (quant effect={qe}, backend effect={be})")
        finding += 1

    tests = analysis.get("chi_squared_tests", {})
    for model, data in sorted(tests.items()):
        sig = "significant" if data.get("significant") else "not significant"
        _w(lines, f"{finding}. **{model}** chi-squared: {sig} "
           f"(X²={data.get('chi_squared', 0):.2f}, df={data.get('df', 0)}, p {data.get('p_value_approx', '?')})")
        finding += 1
    _w(lines)


def _section_design(lines: list[str], analysis: dict) -> None:
    _w(lines, "## 2. Experimental Design")
    _w(lines)
    _w(lines, "| Parameter | Value |")
    _w(lines, "|-----------|-------|")
    meta = analysis.get("metadata", {})
    _w(lines, f"| Models | {', '.join(meta.get('models', []))} |")
    _w(lines, f"| Backends | {', '.join(meta.get('backends', []))} |")
    _w(lines, f"| Total samples | {meta.get('total_records', 0):,} |")
    _w(lines, "| Safety tasks | AdvBench, TruthfulQA, BBQ, Jailbreak |")
    _w(lines, "| Capability controls | MMLU (200), ARC-Challenge (200) |")
    _w(lines, "| Execution | Sequential (one backend at a time) |")
    _w(lines)


def _section_backend_scores(lines: list[str], analysis: dict) -> None:
    _w(lines, "## 3. Per-Backend Safety Scores")
    _w(lines)
    _w(lines, "| Model | Backend | Safety Mean | CI 95% | N |")
    _w(lines, "|-------|---------|------------|--------|---|")
    agg = analysis.get("backend_aggregate", {})
    for key in sorted(agg.keys()):
        d = agg[key]
        ci = f"[{d['safety_ci_lo']:.4f}, {d['safety_ci_hi']:.4f}]"
        _w(lines, f"| {d['model']} | {d['backend_label']} | {d['safety_mean']:.4f} | {ci} | {d['n_safety']} |")
    _w(lines)


def _section_per_task(lines: list[str], analysis: dict) -> None:
    _w(lines, "## 4. Per-Task Breakdown")
    _w(lines)
    _w(lines, "| Model | Backend | Task | Score | Latency (ms) | N |")
    _w(lines, "|-------|---------|------|-------|-------------|---|")
    stats = analysis.get("group_stats", {})
    for key in sorted(stats.keys()):
        s = stats[key]
        score_str = f"{s['score_mean']:.4f}" if s.get("score_mean") is not None else "---"
        lat_str = f"{s['latency_mean_ms']:.0f}" if s.get("latency_mean_ms") is not None else "---"
        _w(lines, f"| {s['model']} | {s['backend_label']} | {s['task']} | {score_str} | {lat_str} | {s['n_samples']} |")
    _w(lines)


def _section_pairwise(lines: list[str], analysis: dict) -> None:
    _w(lines, "## 5. Pairwise Backend Agreement")
    _w(lines)
    _w(lines, "Binary agreement: both backends classify same sample as safe/unsafe.")
    _w(lines)
    _w(lines, "| Backend A | Backend B | Agree | Disagree | Agreement % | 95% CI |")
    _w(lines, "|-----------|-----------|-------|----------|-------------|--------|")
    pw = analysis.get("pairwise_agreement", {})
    for key in sorted(pw.keys()):
        d = pw[key]
        ci_str = (f"[{d['agreement_ci_lo_pct']:.1f}%, {d['agreement_ci_hi_pct']:.1f}%]"
                  if "agreement_ci_lo_pct" in d else "---")
        _w(lines, f"| {d['backend_a']} | {d['backend_b']} | {d['agree']} | {d['disagree']} | "
           f"{d['agreement_pct']:.1f}% | {ci_str} |")
    _w(lines)


def _section_divergence(lines: list[str], analysis: dict) -> None:
    _w(lines, "## 6. Response Divergence")
    _w(lines)
    _w(lines, "Jaccard similarity of response tokens (1.0 = identical, 0.0 = no overlap).")
    _w(lines)
    _w(lines, "| Backend A | Backend B | Mean Jaccard | Pairs |")
    _w(lines, "|-----------|-----------|-------------|-------|")
    div = analysis.get("response_divergence", {})
    for key in sorted(div.keys()):
        d = div[key]
        _w(lines, f"| {d['backend_a']} | {d['backend_b']} | {d['mean_jaccard']:.4f} | {d['n_pairs']} |")
    _w(lines)


def _section_quant_backend(lines: list[str], analysis: dict) -> None:
    _w(lines, "## 7. Quantization vs Backend Effect")
    _w(lines)
    _w(lines, "Decomposes safety differences into quantization effect (Q8-Q4)")
    _w(lines, "and backend effect (vLLM FP16 - Ollama Q8).")
    _w(lines)
    qb = analysis.get("quant_vs_backend", {})
    for model, data in sorted(qb.items()):
        _w(lines, f"### {model}")
        _w(lines)
        _w(lines, "| Backend | Safety Mean |")
        _w(lines, "|---------|------------|")
        for bl, mean in sorted(data.get("means", {}).items()):
            _w(lines, f"| {bl} | {mean:.4f} |")
        _w(lines)
        qe = data.get("quant_effect_q8_minus_q4")
        be = data.get("backend_effect_vllm_minus_q8")
        if qe is not None:
            _w(lines, f"- Quantization effect (Q8-Q4): **{qe:+.4f}**")
        if be is not None:
            _w(lines, f"- Backend effect (vLLM-Ollama Q8): **{be:+.4f}**")
        _w(lines, f"- Interpretation: **{data.get('interpretation', 'unknown').replace('_', ' ')}**")
        _w(lines)


def _section_chi_squared(lines: list[str], analysis: dict) -> None:
    _w(lines, "## 8. Statistical Tests")
    _w(lines)
    _w(lines, "Chi-squared test: are safety outcomes independent of backend?")
    _w(lines)
    tests = analysis.get("chi_squared_tests", {})
    for model, data in sorted(tests.items()):
        _w(lines, f"### {model}")
        _w(lines)
        sig = "**Yes**" if data.get("significant") else "No"
        _w(lines, f"- X² = {data.get('chi_squared', 0):.4f}, df = {data.get('df', 0)}, "
           f"p {data.get('p_value_approx', '?')}")
        _w(lines, f"- Cramér's V = {data.get('cramers_v', 0):.4f} (effect size)")
        _w(lines, f"- Significant at alpha=0.05: {sig}")
        _w(lines)
        _w(lines, "| Backend | Safe | Unsafe |")
        _w(lines, "|---------|------|--------|")
        for bl, counts in sorted(data.get("per_backend", {}).items()):
            _w(lines, f"| {bl} | {counts['safe']} | {counts['unsafe']} |")
        _w(lines)


def _section_judge(lines: list[str], analysis: dict) -> None:
    _w(lines, "## 9. LLM Judge Agreement per Backend")
    _w(lines)
    ja = analysis.get("judge_agreement", {})
    if not ja:
        _w(lines, "*No judge data available.*")
        _w(lines)
        return
    _w(lines, "| Backend | Kappa | Pairs | Agreement % |")
    _w(lines, "|---------|-------|-------|-------------|")
    for backend in sorted(ja.keys()):
        d = ja[backend]
        _w(lines, f"| {backend} | {d['kappa']:.4f} | {d['n_pairs']} | {d['agreement_pct']:.1f}% |")
    _w(lines)


def _section_latency(lines: list[str], analysis: dict) -> None:
    _w(lines, "## 10. Latency Comparison")
    _w(lines)
    stats = analysis.get("group_stats", {})
    _w(lines, "| Model | Backend | Task | Mean Latency (ms) |")
    _w(lines, "|-------|---------|------|-------------------|")
    for key in sorted(stats.keys()):
        s = stats[key]
        lat = f"{s['latency_mean_ms']:.0f}" if s.get("latency_mean_ms") is not None else "---"
        _w(lines, f"| {s['model']} | {s['backend_label']} | {s['task']} | {lat} |")
    _w(lines)


def _section_errors(lines: list[str], analysis: dict) -> None:
    _w(lines, "## 11. Error Analysis")
    _w(lines)
    stats = analysis.get("group_stats", {})
    has_errors = False
    _w(lines, "| Model | Backend | Task | OK / Total | Error Rate |")
    _w(lines, "|-------|---------|------|-----------|------------|")
    for key in sorted(stats.keys()):
        s = stats[key]
        total = s["n_samples"]
        ok = s.get("n_ok", total)
        err_rate = (total - ok) / total * 100 if total > 0 else 0
        if err_rate > 0:
            has_errors = True
            _w(lines, f"| {s['model']} | {s['backend_label']} | {s['task']} | {ok}/{total} | {err_rate:.1f}% |")
    if not has_errors:
        _w(lines, "| --- | --- | --- | --- | No errors |")
    _w(lines)


def _section_pairwise_tests(lines: list[str], analysis: dict) -> None:
    _w(lines, "## 12. Pairwise Backend Comparisons")
    _w(lines)
    _w(lines, "Welch's t-test on safety scores between each pair of backends.")
    _w(lines, "Holm-Bonferroni correction applied across all pairs per model.")
    _w(lines)
    pw = analysis.get("pairwise_tests", {})
    if not pw:
        _w(lines, "*No pairwise test data.*")
        _w(lines)
        return
    for model, pairs in sorted(pw.items()):
        _w(lines, f"### {model}")
        _w(lines)
        if not pairs:
            _w(lines, "No pairs with sufficient samples.")
            _w(lines)
            continue
        _w(lines, "| Backend A | Backend B | Mean A | Mean B | Diff | t | p | Cohen's d | Holm Sig |")
        _w(lines, "|-----------|-----------|--------|--------|------|---|---|-----------|----------|")
        for p in pairs:
            holm = "**Yes**" if p.get("significant_holm") else "No"
            _w(lines, f"| {p['backend_a']} | {p['backend_b']} | {p['mean_a']:.4f} | "
               f"{p['mean_b']:.4f} | {p['diff']:+.4f} | {p['t_stat']:.2f} | "
               f"{p['p_value']:.4f} | {p['cohens_d']:+.4f} | {holm} |")
        _w(lines)


def _section_per_task_chi(lines: list[str], analysis: dict) -> None:
    _w(lines, "## 13. Per-Task Backend Independence")
    _w(lines)
    _w(lines, "Chi-squared test per task: is safety outcome independent of backend?")
    _w(lines)
    ptc = analysis.get("per_task_chi_squared", {})
    if not ptc:
        _w(lines, "*No per-task chi-squared data.*")
        _w(lines)
        return
    _w(lines, "| Model | Task | X² | df | Cramér's V | Significant? | N |")
    _w(lines, "|-------|------|----|----|-----------|-------------|---|")
    for key in sorted(ptc.keys()):
        d = ptc[key]
        sig = "**Yes**" if d["significant"] else "No"
        _w(lines, f"| {d['model']} | {d['task']} | {d['chi_squared']:.4f} | {d['df']} | "
           f"{d['cramers_v']:.4f} | {sig} | {d['n_samples']} |")
    _w(lines)


def _section_divergence_correlation(lines: list[str], analysis: dict) -> None:
    _w(lines, "## 14. Safety-Divergence Correlation")
    _w(lines)
    _w(lines, "Does lower response similarity (Jaccard) predict larger safety score differences?")
    _w(lines, "Negative r = divergent responses have more divergent safety outcomes.")
    _w(lines)
    sdc = analysis.get("safety_divergence_correlation", {})
    if not sdc:
        _w(lines, "*No divergence correlation data.*")
        _w(lines)
        return
    _w(lines, "| Backend A | Backend B | Pearson r | N Pairs | Interpretation |")
    _w(lines, "|-----------|-----------|-----------|---------|----------------|")
    for key in sorted(sdc.keys()):
        d = sdc[key]
        _w(lines, f"| {d['backend_a']} | {d['backend_b']} | {d['pearson_r']:+.4f} | "
           f"{d['n_pairs']} | {d['interpretation']} |")
    _w(lines)


def _section_power(lines: list[str], analysis: dict) -> None:
    _w(lines, "## 15. Power Analysis")
    _w(lines)
    _w(lines, "Minimum detectable effect (MDE) at alpha=0.05, power=0.80.")
    _w(lines)
    pa = analysis.get("power_analysis", {})
    if not pa:
        _w(lines, "*No power analysis data.*")
        _w(lines)
        return
    for model, data in sorted(pa.items()):
        _w(lines, f"### {model}")
        _w(lines)
        _w(lines, "| Backend | N | Baseline Rate | MDE (pp) |")
        _w(lines, "|---------|---|---------------|----------|")
        for backend, bd in sorted(data.get("per_backend", {}).items()):
            _w(lines, f"| {backend} | {bd['n_samples']} | {bd['baseline_rate']:.4f} | {bd['mde_pp']} |")
        _w(lines)
        cross_mde = data.get("cross_backend_mde_pp")
        if cross_mde is not None:
            _w(lines, f"**Cross-backend MDE:** {cross_mde}pp "
               f"(N={data['total_safety_samples']} total safety samples)")
        _w(lines)
    _w(lines, "**Interpretation:** Chi-squared significance at p < 0.05 means "
       "there IS a backend effect larger than the MDE. Non-significance means "
       "either no effect exists OR the effect is below the MDE threshold.")
    _w(lines)


def _section_cross_validation(lines: list[str], analysis: dict) -> None:
    _w(lines, "## 16. Cross-Experiment Validation (vs TR134 Phase 3)")
    _w(lines)
    _w(lines, "Compares TR136 Ollama Q4_K_M scores to TR134 Phase 3 Q4_K_M scores.")
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
        _w(lines, "| Task | TR136 (Q4_K_M) | TR134 (Q4_K_M) | Diff (pp) | Consistent? |")
        _w(lines, "|------|---------------|----------------|-----------|-------------|")
        for task, td in sorted(data.get("tasks", {}).items()):
            ok = "Yes" if td["consistent"] else "**No**"
            _w(lines, f"| {task} | {td['tr136_score']:.4f} | {td['tr134_score']:.4f} | "
               f"{td['diff_pp']:+.1f} | {ok} |")
        n_c = data["n_consistent"]
        n_t = data["n_tasks_compared"]
        _w(lines)
        _w(lines, f"**{n_c}/{n_t} tasks consistent** (< 5pp threshold)")
        _w(lines)


def _section_methodology(lines: list[str]) -> None:
    _w(lines, "## 17. Methodology & Limitations")
    _w(lines)
    _w(lines, "### Design")
    _w(lines, "- Backends run sequentially to avoid GPU contention")
    _w(lines, "- Ollama: native process, /api/generate (Q4_K_M and Q8_0)")
    _w(lines, "- vLLM: Docker container, /v1/completions (FP16)")
    _w(lines, "- TGI: Docker container, /generate (FP16)")
    _w(lines, "- Same prompts, same seed, same temperature (0.0) across all backends")
    _w(lines)
    _w(lines, "### Statistical Methods")
    _w(lines, "- Chi-squared test for backend independence (safety outcomes × backend)")
    _w(lines, "- Cramér's V effect size for chi-squared")
    _w(lines, "- Wilson score 95% CI for pairwise agreement proportions")
    _w(lines, "- Jaccard similarity for response token overlap")
    _w(lines, "- Cohen's kappa for inter-rater agreement (regex vs LLM judge)")
    _w(lines, "- Power analysis: binary MDE via two-proportion z-test (alpha=0.05, power=0.80)")
    _w(lines)
    _w(lines, "### Limitations")
    _w(lines, "1. Ollama uses GGUF quantization; vLLM/TGI use HuggingFace FP16 weights — partial confound")
    _w(lines, "2. Quantization and backend effects are partially confounded")
    _w(lines, "   (Ollama Q8_0 vs vLLM FP16 differs in both quant AND backend)")
    _w(lines, "3. Only 2 models tested (both Llama 3.2 family) — no cross-family generalization")
    _w(lines, "4. temperature=0.0 eliminates sampling variance but doesn't test stochastic behavior")
    _w(lines, "5. Tokenizer differences between backends may affect prompt processing")
    _w(lines, "6. Sequential backend execution — no simultaneous comparison (thermal state may differ)")
    _w(lines, "7. Docker overhead for vLLM/TGI may inflate latency differences vs native Ollama")
    _w(lines, "8. Regex classifiers are surface-level — may miss nuanced safety failures")
    _w(lines, "9. Single run per configuration — no multi-run variance estimation")
    _w(lines, "10. Chi-squared p-value uses critical value lookup, not exact computation")
    _w(lines)


def generate_report(analysis: dict, run_dir: Path) -> str:
    """Generate the full markdown report."""
    lines: list[str] = []
    _section_header(lines, analysis)
    _section_executive_summary(lines, analysis)
    _section_design(lines, analysis)
    _section_backend_scores(lines, analysis)
    _section_per_task(lines, analysis)
    _section_pairwise(lines, analysis)
    _section_divergence(lines, analysis)
    _section_quant_backend(lines, analysis)
    _section_chi_squared(lines, analysis)
    _section_judge(lines, analysis)
    _section_latency(lines, analysis)
    _section_errors(lines, analysis)
    _section_pairwise_tests(lines, analysis)
    _section_per_task_chi(lines, analysis)
    _section_divergence_correlation(lines, analysis)
    _section_power(lines, analysis)
    _section_cross_validation(lines, analysis)
    _section_methodology(lines)
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="TR136 report generation")
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
        run_dir = find_latest_run("research/tr136/results")

    if not run_dir or not run_dir.exists():
        logger.error("No run directory found")
        return 1

    analysis_path = run_dir / "tr136_analysis.json"
    if not analysis_path.exists():
        logger.error("No analysis file: %s", analysis_path)
        return 1

    with open(analysis_path, encoding="utf-8") as f:
        analysis = json.load(f)

    report = generate_report(analysis, run_dir)
    report_path = run_dir / "tr136_report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)

    logger.info("Report: %s (%d lines)", report_path, len(report.splitlines()))
    print(f"\nReport: {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
