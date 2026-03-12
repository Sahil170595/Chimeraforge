"""TR124 Phase 2: Generate quantization quality impact report.

Reads framework output + Phase 2 analysis and produces a markdown report.

Usage:
    python research/tr124/phase2/generate_report.py [--results-dir DIR]
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
    aggregate_by_group,
    compute_metric_summaries,
    load_sample_jsonl,
)

logger = logging.getLogger("tr124.phase2.report")

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


def generate_phase2_report(
    run_dir: Path,
    records: list[SampleRecord],
    analysis: dict[str, Any],
) -> Path:
    """Generate Phase 2 markdown report."""
    lines: list[str] = []
    gen_records = [r for r in records if r.task_type != "multiple_choice"]
    degrad = analysis.get("degradation_table", [])
    comparisons = analysis.get("pairwise_comparisons", [])

    # Header
    _w(lines, "# TR124 Phase 2: Quantization Quality Impact")
    _w(lines)
    _w(lines, f"**Date:** {datetime.now(UTC).strftime('%Y-%m-%d')}")
    _w(lines, f"**Total Samples:** {len(gen_records)}")
    _w(
        lines,
        f"**Phase 1 Baselines:** {'loaded' if analysis.get('phase1_baselines_loaded') else 'not available'}",
    )
    _w(lines)
    _w(lines, "---")
    _w(lines)

    # Executive summary
    _w(lines, "## Executive Summary")
    _w(lines)

    # Summarise FP16 cross-phase deltas (the useful comparison)
    fp16_deltas: list[tuple[str, str, float]] = []  # (model, metric, pct)
    for row in degrad:
        for m in ["bertscore", "coherence", "rouge_l"]:
            d = row.get(f"{m}_delta_fp16_pct")
            if d is not None:
                fp16_deltas.append((row["base_model"], m, d))

    if fp16_deltas:
        worst = min(fp16_deltas, key=lambda x: x[2])
        best = max(fp16_deltas, key=lambda x: x[2])
        avg_delta = sum(d for _, _, d in fp16_deltas) / len(fp16_deltas)

        _w(
            lines,
            f"**Finding 1 — Average Impact:** Quantization changes quality by "
            f"**{avg_delta:+.1f}%** on average across key metrics (bertscore, coherence, "
            f"rouge_l) vs Phase 1 FP16 baselines.",
        )
        _w(lines)
        _w(
            lines,
            f"**Finding 2 — Worst Case:** Largest quality drop is "
            f"**{worst[2]:+.1f}%** ({worst[0]} on {worst[1]}).",
        )
        _w(lines)
        _w(
            lines,
            f"**Finding 3 — Best Case:** Largest quality gain is "
            f"**{best[2]:+.1f}%** ({best[0]} on {best[1]}).",
        )
    _w(lines)
    _w(lines, "---")
    _w(lines)

    # Degradation table — cross-phase comparison vs Phase 1 FP16
    _w(lines, "## Quantization Quality vs Phase 1 FP16 Baseline")
    _w(lines)
    _w(
        lines,
        "Delta% = (Ollama quant score - Phase 1 FP16 score) / FP16 score × 100. "
        "Negative = quality loss from quantization.",
    )
    _w(lines)

    key_metrics = ["bertscore", "coherence", "rouge_l"]

    _w(
        lines,
        "| Model | Quant | N | "
        + " | ".join(f"{m} (vs FP16)" for m in key_metrics)
        + " | Composite |",
    )
    _w(
        lines,
        "|-------|-------|---|"
        + "|".join("---" for _ in key_metrics)
        + "|-----------|",
    )

    for row in sorted(degrad, key=lambda r: r.get("base_model", "")):
        cols = [
            row.get("base_model", "?"),
            row.get("quant_level", "?"),
            str(row.get("n_samples", 0)),
        ]
        for m in key_metrics:
            mean_val = row.get(f"{m}_mean")
            delta_pct = row.get(f"{m}_delta_fp16_pct")
            if mean_val is not None and delta_pct is not None:
                cols.append(f"{mean_val:.3f} ({delta_pct:+.1f}%)")
            elif mean_val is not None:
                cols.append(f"{mean_val:.3f} (no baseline)")
            else:
                cols.append("---")
        composite = row.get("composite_quality")
        cols.append(f"{composite:.4f}" if composite is not None else "---")
        _w(lines, "| " + " | ".join(cols) + " |")
    _w(lines)

    _w(lines, "---")
    _w(lines)

    # Pairwise significance
    _w(lines, "## Statistical Tests: Quant Level Comparisons")
    _w(lines)
    _w(lines, "Pairwise t-tests within each base model across quantization levels.")
    _w(lines)

    if comparisons:
        _w(
            lines,
            "| Base Model | Metric | Q_A | Q_B | Mean A | Mean B | "
            "Cohen's d | p-value | Sig? |",
        )
        _w(
            lines,
            "|------------|--------|-----|-----|--------|--------|"
            "-----------|---------|------|",
        )
        for c in sorted(comparisons, key=lambda x: (x["base_model"], x["metric"])):
            sig = "**YES**" if c["significant"] else "no"
            _w(
                lines,
                f"| {c['base_model']} | {c['metric']} "
                f"| {c['quant_a']} | {c['quant_b']} "
                f"| {c['mean_a']:.4f} | {c['mean_b']:.4f} "
                f"| {c['effect_size']:.3f} | {c['p_value']:.4f} | {sig} |",
            )
        _w(lines)
    else:
        _w(
            lines,
            "*No pairwise comparisons available (need >= 2 quant levels per model).*",
        )
        _w(lines)

    _w(lines, "---")
    _w(lines)

    # Per-task quality
    _w(lines, "## Per-Task Quality by Model Variant")
    _w(lines)
    task_groups = aggregate_by_group(gen_records, ["task_name"])
    for (task_name,), task_records in sorted(task_groups.items()):
        _w(lines, f"### {task_name}")
        _w(lines)
        model_groups = aggregate_by_group(task_records, ["model"])
        _w(lines, "| Model | " + " | ".join(QUALITY_METRICS) + " |")
        _w(lines, "|-------|" + "|".join("---" for _ in QUALITY_METRICS) + "|")
        for (model,), recs in sorted(model_groups.items()):
            summaries = compute_metric_summaries(recs, QUALITY_METRICS)
            cols = []
            for m in QUALITY_METRICS:
                if m in summaries:
                    cols.append(f"{summaries[m].mean:.4f}")
                else:
                    cols.append("---")
            _w(lines, f"| {model} | " + " | ".join(cols) + " |")
        _w(lines)

    _w(lines, "---")
    _w(lines)

    # Recommendations
    _w(lines, "## Findings & Recommendations")
    _w(lines)
    _w(lines, "### Quantization Guidance")
    _w(lines)
    _w(lines, "- Quality degradation < 5%: Q4_K_M is safe for production")
    _w(lines, "- Quality degradation 5-10%: Use Q8_0 for quality-sensitive tasks")
    _w(lines, "- Quality degradation > 10%: Prefer FP16 (Phase 1 baseline)")
    _w(
        lines,
        "- Cross-reference with TR123 cost data for quality-adjusted cost rankings",
    )
    _w(lines)
    _w(lines, "### Limitations")
    _w(lines)
    _w(
        lines,
        "- Ollama's default quant level per model varies; actual precision may differ from tag",
    )
    _w(lines, "- No benchmark accuracy available (Ollama lacks logprob support)")
    _w(lines, "- Single repetition at temp=0 — variance measured in Phase 3")
    _w(lines)

    # Methodology
    _w(lines, "## Methodology")
    _w(lines)
    _w(lines, "- **Backend:** Ollama HTTP API (`/api/generate`)")
    _w(lines, "- **Temperature:** 0.0 (greedy)")
    _w(lines, "- **Repetitions:** 1")
    _w(lines, "- **Metrics:** " + ", ".join(QUALITY_METRICS))
    _w(
        lines,
        "- **Delta reference:** Phase 1 FP16 baselines (transformers-gpu backend)",
    )
    _w(
        lines,
        "- **Quantization levels:** Ollama defaults (Q8_0 for small models, Q4_K_M/Q4_0 for larger)",
    )
    _w(lines)

    # Write
    report_path = run_dir / "phase2_report.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Wrote Phase 2 report: %s", report_path)
    return report_path


def main() -> int:
    parser = argparse.ArgumentParser(description="TR124 Phase 2 report")
    parser.add_argument("--results-dir", default="results/eval/tr124_phase2")
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

    # Load records
    jsonl_path = run_dir / "samples.jsonl"
    if not jsonl_path.exists():
        logger.error("No samples.jsonl in %s", run_dir)
        return 1
    records = load_sample_jsonl(jsonl_path)

    # Load analysis
    analysis_path = run_dir / "phase2_analysis.json"
    if analysis_path.exists():
        analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
    else:
        logger.warning("No phase2_analysis.json — run analyze.py first")
        analysis = {}

    generate_phase2_report(run_dir, records, analysis)
    return 0


if __name__ == "__main__":
    sys.exit(main())
