"""TR124 Phase 3: Generate sampling variance report.

Usage:
    python research/tr124/phase3/generate_report.py [--results-dir DIR]
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
import logging
from pathlib import Path
import sys
from typing import Any

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO))

from research.tr124.shared.utils import find_latest_run
from scripts.eval.analysis.aggregator import (
    SampleRecord,
    load_sample_jsonl,
)

logger = logging.getLogger("tr124.phase3.report")

QUALITY_METRICS = [
    "bertscore",
    "bleu",
    "coherence",
    "exact_match",
    "output_length",
    "repetition",
    "rouge_l",
]


def _w(lines: list[str], text: str = "") -> None:
    lines.append(text)


def generate_phase3_report(
    run_dir: Path,
    records: list[SampleRecord],
    analysis: dict[str, Any],
) -> Path:
    """Generate Phase 3 markdown report."""
    lines: list[str] = []
    gen_records = [r for r in records if r.task_type != "multiple_choice"]
    variance_rows = analysis.get("variance_by_model_backend", [])
    repeatability = analysis.get("repeatability", {})
    levene = analysis.get("levene_tests", {})

    # Header
    _w(lines, "# TR124 Phase 3: Sampling Variance Analysis")
    _w(lines)
    _w(lines, f"**Date:** {datetime.now(UTC).strftime('%Y-%m-%d')}")
    _w(lines, f"**Total Samples:** {len(gen_records)}")
    _w(lines, "**Temperature:** 0.7")
    _w(lines, "**Repetitions:** 5 per sample")
    _w(lines)
    _w(lines, "---")
    _w(lines)

    # Executive summary
    _w(lines, "## Executive Summary")
    _w(lines)
    if "error" not in repeatability:
        pct10 = repeatability.get("pct_cv_under_10", 0)
        mean_cv = repeatability.get("mean_cv", 0)
        if pct10 > 80:
            verdict = "highly reproducible"
            guidance = "Single-run quality estimates are reliable."
        elif pct10 > 50:
            verdict = "moderately reproducible"
            guidance = "Average 3+ runs for reliable quality estimates."
        else:
            verdict = "unstable"
            guidance = "Use greedy decoding (temp=0) for quality evaluation."

        _w(
            lines,
            f"**Finding 1 — Reproducibility:** Quality scores are **{verdict}** "
            f"at temperature=0.7. {pct10:.0f}% of measurements have CV < 10% "
            f"(mean CV = {mean_cv:.4f}). {guidance}",
        )
    _w(lines)

    # Levene finding
    sig_count = sum(
        1
        for v in levene.values()
        if isinstance(v, dict) and v.get("significant", False)
    )
    total_tests = sum(
        1 for v in levene.values() if isinstance(v, dict) and "significant" in v
    )
    if total_tests > 0:
        if sig_count == 0:
            _w(
                lines,
                f"**Finding 2 — Variance Equality:** Backends produce "
                f"equal variance ({sig_count}/{total_tests} metrics significant "
                f"on Levene's test). torch.compile does not alter output diversity.",
            )
        else:
            _w(
                lines,
                f"**Finding 2 — Variance Divergence:** {sig_count}/{total_tests} "
                f"metrics show backends produce different output variance.",
            )
    _w(lines)
    _w(lines, "---")
    _w(lines)

    # Repeatability overview
    _w(lines, "## Repeatability Overview")
    _w(lines)
    if "error" not in repeatability:
        _w(lines, "| Statistic | Value |")
        _w(lines, "|-----------|-------|")
        _w(lines, f"| Measurements | {repeatability.get('n_measurements', 0)} |")
        _w(lines, f"| Mean CV | {repeatability.get('mean_cv', 0):.4f} |")
        _w(lines, f"| Median CV | {repeatability.get('median_cv', 0):.4f} |")
        _w(lines, f"| Max CV | {repeatability.get('max_cv', 0):.4f} |")
        _w(
            lines,
            f"| CV < 5% (very stable) | {repeatability.get('pct_cv_under_05', 0):.1f}% |",
        )
        _w(
            lines,
            f"| CV < 10% (stable) | {repeatability.get('pct_cv_under_10', 0):.1f}% |",
        )
        _w(
            lines,
            f"| CV < 20% (moderate) | {repeatability.get('pct_cv_under_20', 0):.1f}% |",
        )
    _w(lines)
    _w(lines, "---")
    _w(lines)

    # Per-model variance
    _w(lines, "## Variance by Model, Backend, and Metric")
    _w(lines)
    _w(lines, "CV = coefficient of variation (std / mean). Lower = more reproducible.")
    _w(lines)
    if variance_rows:
        _w(
            lines,
            "| Model | Backend | Metric | Mean Score | Mean CV | Max CV | Stability |",
        )
        _w(
            lines,
            "|-------|---------|--------|-----------|---------|--------|-----------|",
        )
        for row in variance_rows:
            _w(
                lines,
                f"| {row['model']} | {row['backend']} | {row['metric']} "
                f"| {row['grand_mean']:.4f} | {row['mean_cv']:.4f} "
                f"| {row['max_cv']:.4f} | {row['stability']} |",
            )
    _w(lines)
    _w(lines, "---")
    _w(lines)

    # Levene's test
    _w(lines, "## Backend Variance Equality (Levene's Test)")
    _w(lines)
    _w(
        lines,
        "Brown-Forsythe variant: do backends produce different amounts of "
        "output variance?",
    )
    _w(lines)
    if levene and "error" not in levene:
        _w(lines, "| Metric | F-statistic | p-value | Significant? |")
        _w(lines, "|--------|-------------|---------|--------------|")
        for metric, result in sorted(levene.items()):
            if isinstance(result, dict) and "statistic" in result:
                sig = "**YES**" if result["significant"] else "no"
                _w(
                    lines,
                    f"| {metric} | {result['statistic']:.3f} "
                    f"| {result['p_value']:.4f} | {sig} |",
                )
            elif isinstance(result, dict):
                _w(lines, f"| {metric} | --- | --- | {result.get('error', 'N/A')} |")
    _w(lines)
    _w(lines, "---")
    _w(lines)

    # Phase 1 comparison note
    _w(lines, "## Phase 1 vs Phase 3 Comparison")
    _w(lines)
    _w(
        lines,
        "Phase 1 (temp=0.0) established mean quality baselines. Phase 3 "
        "(temp=0.7) measures the variance envelope around those means.",
    )
    _w(lines)
    _w(
        lines,
        "- Error bars from Phase 3 should be applied to Phase 1 baselines "
        "when making production deployment decisions",
    )
    _w(
        lines,
        "- If a model's Phase 1 quality edge is smaller than Phase 3's "
        "variance, the ranking is unreliable under realistic sampling",
    )
    _w(lines)
    _w(lines, "---")
    _w(lines)

    # Methodology
    _w(lines, "## Methodology")
    _w(lines)
    _w(lines, "- **Temperature:** 0.7 (non-greedy)")
    _w(lines, "- **Repetitions:** 5 per (model, backend, task, sample)")
    _w(lines, "- **Variance metric:** Coefficient of Variation (CV = std / mean)")
    _w(lines, "- **Variance equality:** Brown-Forsythe test (Levene with median)")
    _w(lines, "- **Quality metrics:** " + ", ".join(QUALITY_METRICS))
    _w(lines)

    # Write
    report_path = run_dir / "phase3_report.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Wrote Phase 3 report: %s", report_path)
    return report_path


def main() -> int:
    parser = argparse.ArgumentParser(description="TR124 Phase 3 report")
    parser.add_argument("--results-dir", default="results/eval/tr124_phase3")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    run_dir = find_latest_run(args.results_dir)
    if run_dir is None:
        logger.error("No runs found in %s", args.results_dir)
        return 1

    jsonl_path = run_dir / "samples.jsonl"
    if not jsonl_path.exists():
        logger.error("No samples.jsonl in %s", run_dir)
        return 1
    records = load_sample_jsonl(jsonl_path)

    analysis_path = run_dir / "phase3_analysis.json"
    if analysis_path.exists():
        analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
    else:
        logger.warning("No phase3_analysis.json — run analyze.py first")
        analysis = {}

    generate_phase3_report(run_dir, records, analysis)
    return 0


if __name__ == "__main__":
    sys.exit(main())
