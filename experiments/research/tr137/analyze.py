"""TR137: The Safety Tax — Unified Analysis (18 passes).

Synthesis of TR134 (quant x safety), TR135 (concurrency x safety),
TR136 (backend x safety) into a unified safety-optimization framework.

Passes:
  1: Load and validate source analyses (with schema checks)
  2: Cross-TR baseline validation (shared model anchor points)
  3: Effect size ranking (which optimization axis hurts safety most?)
  4: Safety-capability asymmetry per axis
  5: Per-task vulnerability matrix (task x axis effect sizes)
  6: Quant x concurrency projection (additive model)
  7: Backend x quant decomposition (from TR136)
  8: Jailbreak synthesis across axes
  9: Family-level patterns (Llama vs Qwen vs Mistral)
  10: Model-axis heterogeneity (I-squared: do models agree?)
  11: Safety-adjusted deployment matrix
  12: Worst-case identification
  13: Aggregate power and sensitivity
  14: Per-category bias synthesis (BBQ demographics across axes)
  15: Judge agreement synthesis (regex vs LLM across axes)
  16: Bootstrap CI on cross-axis effect sizes
  17: Cross-axis correlation (models vulnerable on one axis → vulnerable on others?)
  18: Effect decomposition (% contribution per axis)

Usage:
    python research/tr137/analyze.py [-v] [--tr134-dir PATH] [--tr135-dir PATH]
      [--tr136-dir PATH]
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import math
import random
from collections import defaultdict
from pathlib import Path
import sys
from typing import Any

_DIR = Path(__file__).resolve().parent
_REPO = _DIR.parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from research.tr137.shared.env_fingerprint import capture_environment
from research.tr137.shared.utils import (
    ANCHOR_BACKEND,
    ANCHOR_N,
    ANCHOR_QUANT,
    BASELINE_TOLERANCE_PP,
    CAPABILITY_TASKS,
    QUANT_BPW,
    SAFETY_TASKS,
    SHARED_MODELS,
    TASK_METRIC,
    classify_risk,
    detect_source_outliers,
    infer_family,
    load_tr134,
    load_tr135,
    load_tr136,
    validate_analysis,
    validate_source_status,
    TR134_REQUIRED_KEYS,
    TR135_REQUIRED_KEYS,
    TR136_REQUIRED_KEYS,
)

logger = logging.getLogger("tr137.analyze")


# ---------------------------------------------------------------------------
# Score extraction helpers (each TR has different key/field formats)
# ---------------------------------------------------------------------------


def _tr134_score(gs: dict, model: str, quant: str, task: str) -> float | None:
    """Extract mean score from TR134 group_stats."""
    prefix = f"{model}|{quant}|{task}|"
    for key, val in gs.items():
        if key.startswith(prefix):
            return val.get("mean_score")
    return None


def _tr134_stats(gs: dict, model: str, quant: str, task: str) -> dict | None:
    """Extract full stats dict from TR134 group_stats."""
    prefix = f"{model}|{quant}|{task}|"
    for key, val in gs.items():
        if key.startswith(prefix):
            return val
    return None


def _tr134_n(gs: dict, model: str, quant: str, task: str) -> int:
    prefix = f"{model}|{quant}|{task}|"
    for key, val in gs.items():
        if key.startswith(prefix):
            return val.get("n", 0)
    return 0


def _tr135_score(gs: dict, model: str, n: int, task: str) -> float | None:
    """Extract score_mean from TR135 group_stats."""
    key = f"{model}__N{n}__{task}"
    val = gs.get(key)
    return val.get("score_mean") if val else None


def _tr135_stats(gs: dict, model: str, n: int, task: str) -> dict | None:
    key = f"{model}__N{n}__{task}"
    return gs.get(key)


def _tr136_score(gs: dict, model: str, backend: str, task: str) -> float | None:
    """Extract score_mean from TR136 group_stats."""
    key = f"{model}__{backend}__{task}"
    val = gs.get(key)
    return val.get("score_mean") if val else None


def _tr136_stats(gs: dict, model: str, backend: str, task: str) -> dict | None:
    key = f"{model}__{backend}__{task}"
    return gs.get(key)


# ---------------------------------------------------------------------------
# Statistical helpers
# ---------------------------------------------------------------------------


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _std(xs: list[float]) -> float:
    if len(xs) < 2:
        return 0.0
    m = _mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def _cohens_d(
    mean1: float, std1: float, n1: int, mean2: float, std2: float, n2: int
) -> float:
    """Cohen's d with pooled standard deviation."""
    if n1 + n2 < 3:
        return 0.0
    pooled = math.sqrt(((n1 - 1) * std1**2 + (n2 - 1) * std2**2) / (n1 + n2 - 2))
    if pooled < 1e-10:
        return 0.0
    return (mean1 - mean2) / pooled


def _i_squared(effects: list[float], weights: list[float] | None = None) -> float:
    """I-squared heterogeneity statistic."""
    k = len(effects)
    if k < 2:
        return 0.0
    if weights is None:
        weights = [1.0] * k
    w_sum = sum(weights)
    if w_sum < 1e-10:
        return 0.0
    w_mean = sum(w * e for w, e in zip(weights, effects)) / w_sum
    q = sum(w * (e - w_mean) ** 2 for w, e in zip(weights, effects))
    df = k - 1
    if q <= df:
        return 0.0
    return max(0.0, (q - df) / q * 100)


def _pearson_r(xs: list[float], ys: list[float]) -> float | None:
    """Pearson correlation coefficient. Returns None if insufficient data."""
    if len(xs) < 3 or len(xs) != len(ys):
        return None
    mx, my = _mean(xs), _mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if dx < 1e-10 or dy < 1e-10:
        return None
    return num / (dx * dy)


def _bootstrap_ci(
    values: list[float], n_boot: int = 2000, confidence: float = 0.95, seed: int = 42
) -> dict:
    """Bootstrap confidence interval on the mean."""
    if len(values) < 2:
        m = _mean(values)
        return {"mean": m, "ci_lower": m, "ci_upper": m, "n_boot": 0}
    rng = random.Random(seed)
    n = len(values)
    boot_means = []
    for _ in range(n_boot):
        sample = [values[rng.randint(0, n - 1)] for _ in range(n)]
        boot_means.append(_mean(sample))
    boot_means.sort()
    alpha = (1 - confidence) / 2
    lo = boot_means[int(alpha * len(boot_means))]
    hi = boot_means[int((1 - alpha) * len(boot_means))]
    return {
        "mean": round(_mean(values), 4),
        "ci_lower": round(lo, 4),
        "ci_upper": round(hi, 4),
        "std": round(_std(values), 4),
        "n_boot": n_boot,
    }


# ---------------------------------------------------------------------------
# Main analysis
# ---------------------------------------------------------------------------


def analyze(
    tr134_dir: Path | None = None,
    tr135_dir: Path | None = None,
    tr136_dir: Path | None = None,
) -> dict[str, Any]:
    """Run all 18 synthesis passes."""

    # === Pass 1: Load and validate ===
    logger.info("Pass 1/18: Loading and validating source analyses...")
    tr134 = load_tr134(tr134_dir)
    tr135 = load_tr135(tr135_dir)
    tr136 = load_tr136(tr136_dir)

    available = {"tr134": bool(tr134), "tr135": bool(tr135), "tr136": bool(tr136)}
    n_sources = sum(available.values())

    if n_sources == 0:
        logger.error("No source data available — cannot run synthesis")
        return {}

    logger.info("Sources available: %s (%d/3)", available, n_sources)

    # Validate each source (schema + status)
    validation_warnings: list[str] = []
    if available["tr134"]:
        validation_warnings.extend(
            validate_analysis(tr134, TR134_REQUIRED_KEYS, "TR134")
        )
        validation_warnings.extend(validate_source_status(tr134, "TR134"))
    if available["tr135"]:
        validation_warnings.extend(
            validate_analysis(tr135, TR135_REQUIRED_KEYS, "TR135")
        )
        validation_warnings.extend(validate_source_status(tr135, "TR135"))
    if available["tr136"]:
        validation_warnings.extend(
            validate_analysis(tr136, TR136_REQUIRED_KEYS, "TR136")
        )
        validation_warnings.extend(validate_source_status(tr136, "TR136"))
    for w in validation_warnings:
        logger.warning("Validation: %s", w)

    # Outlier detection on source data
    logger.info("Pass 1b: Outlier detection on source data...")
    outlier_reports: dict[str, dict] = {}
    if available["tr134"]:
        outlier_reports["tr134"] = detect_source_outliers(tr134, "TR134")
        n_out = outlier_reports["tr134"]["n_outliers_total"]
        if n_out > 0:
            logger.warning("TR134: %d outlier group(s) detected", n_out)
    if available["tr135"]:
        outlier_reports["tr135"] = detect_source_outliers(tr135, "TR135")
        n_out = outlier_reports["tr135"]["n_outliers_total"]
        if n_out > 0:
            logger.warning("TR135: %d outlier group(s) detected", n_out)
    if available["tr136"]:
        outlier_reports["tr136"] = detect_source_outliers(tr136, "TR136")
        n_out = outlier_reports["tr136"]["n_outliers_total"]
        if n_out > 0:
            logger.warning("TR136: %d outlier group(s) detected", n_out)

    # Capture environment
    environment = capture_environment()

    # Extract per-source metadata
    source_meta: dict[str, dict] = {}
    if available["tr134"]:
        m134 = tr134.get("metadata", {})
        source_meta["tr134"] = {
            "total_records": m134.get("total_records", 0),
            "n_models": m134.get("n_models", 0),
            "n_quants": m134.get("n_quants", 0),
            "safety_tasks": m134.get("safety_tasks", []),
            "capability_tasks": m134.get("capability_tasks", []),
        }
    if available["tr135"]:
        m135 = tr135.get("metadata", {})
        source_meta["tr135"] = {
            "total_records": m135.get("total_raw_records", 0),
            "n_models": m135.get("n_models", 0),
            "n_levels": m135.get("n_levels", []),
        }
    if available["tr136"]:
        m136 = tr136.get("metadata", {})
        source_meta["tr136"] = {
            "total_records": m136.get("total_records", 0),
            "n_models": m136.get("n_models", 0),
            "n_backends": m136.get("n_backends", 0),
        }

    total_samples = sum(s.get("total_records", 0) for s in source_meta.values())

    metadata = {
        "experiment": "tr137_safety_tax",
        "sources_available": available,
        "n_sources": n_sources,
        "total_samples_across_trs": total_samples,
        "source_meta": source_meta,
        "validation_warnings": validation_warnings,
        "environment": environment,
        "outlier_summary": {
            label: {
                "n_outliers": r.get("n_outliers_total", 0),
                "n_groups": r.get("n_groups", 0),
                "flagged_groups": r.get("flagged_groups", []),
            }
            for label, r in outlier_reports.items()
        },
    }

    # === Pass 2: Cross-TR baseline validation ===
    logger.info("Pass 2/18: Cross-TR baseline validation...")
    cross_validation = _pass_cross_validation(tr134, tr135, tr136, available)

    # === Pass 3: Effect size ranking ===
    logger.info("Pass 3/18: Effect size ranking across axes...")
    effect_sizes = _pass_effect_sizes(tr134, tr135, tr136, available)

    # === Pass 4: Safety-capability asymmetry ===
    logger.info("Pass 4/18: Safety-capability asymmetry per axis...")
    asymmetry = _pass_asymmetry(tr134, tr135, tr136, available)

    # === Pass 5: Per-task vulnerability matrix ===
    logger.info("Pass 5/18: Per-task vulnerability matrix...")
    task_vuln = _pass_task_vulnerability(tr134, tr135, tr136, available)

    # === Pass 6: Quant x concurrency projection ===
    logger.info("Pass 6/18: Quant x concurrency projection...")
    interaction_qc = _pass_qc_interaction(tr134, tr135, available)

    # === Pass 7: Backend x quant decomposition ===
    logger.info("Pass 7/18: Backend x quant decomposition...")
    backend_quant: dict[str, Any] = {}
    if available["tr136"]:
        qvb = tr136.get("quant_vs_backend", {})
        for model, data in qvb.items():
            if isinstance(data, dict):
                backend_quant[model] = data

    # === Pass 8: Jailbreak synthesis ===
    logger.info("Pass 8/18: Jailbreak synthesis across axes...")
    jailbreak_synth = _pass_jailbreak_synthesis(tr134, tr135, available)

    # === Pass 9: Family-level patterns ===
    logger.info("Pass 9/18: Family-level patterns...")
    family_patterns = _pass_family_patterns(tr134, available, effect_sizes)

    # === Pass 10: Model-axis heterogeneity (I-squared) ===
    logger.info("Pass 10/18: Model-axis heterogeneity...")
    heterogeneity = _pass_heterogeneity(effect_sizes)

    # === Pass 11: Safety-adjusted deployment matrix ===
    logger.info("Pass 11/18: Safety-adjusted deployment matrix...")
    deployment_matrix = _pass_deployment_matrix(
        tr134, tr135, tr136, available, effect_sizes
    )

    # === Pass 12: Worst-case identification ===
    logger.info("Pass 12/18: Worst-case identification...")
    worst_cases = _pass_worst_cases(effect_sizes, deployment_matrix)

    # === Pass 13: Aggregate power and sensitivity ===
    logger.info("Pass 13/18: Aggregate power and sensitivity...")
    power_agg = _pass_power_analysis(tr134, tr135, tr136, available)

    # === Pass 14: Per-category bias synthesis ===
    logger.info("Pass 14/18: Per-category bias synthesis...")
    bias_synthesis = _pass_bias_synthesis(tr134, tr135, tr136, available)

    # === Pass 15: Judge agreement synthesis ===
    logger.info("Pass 15/18: Judge agreement synthesis...")
    judge_synthesis = _pass_judge_synthesis(tr134, tr135, tr136, available)

    # === Pass 16: Bootstrap CI on effect sizes ===
    logger.info("Pass 16/18: Bootstrap CI on cross-axis effects...")
    effect_cis = _pass_bootstrap_effects(effect_sizes)

    # === Pass 17: Cross-axis correlation ===
    logger.info("Pass 17/18: Cross-axis correlation...")
    correlation = _pass_cross_axis_correlation(effect_sizes)

    # === Pass 18: Effect decomposition ===
    logger.info("Pass 18/18: Effect decomposition...")
    decomposition = _pass_effect_decomposition(effect_sizes)

    # === Headline numbers ===
    headlines = _compute_headlines(
        effect_sizes,
        asymmetry,
        deployment_matrix,
        worst_cases,
        total_samples,
        n_sources,
        correlation,
    )

    logger.info(
        "Analysis complete: 18 passes, %d sources, %d total samples",
        n_sources,
        total_samples,
    )

    return {
        "metadata": metadata,
        "cross_validation": cross_validation,
        "effect_sizes": effect_sizes,
        "effect_cis": effect_cis,
        "asymmetry": asymmetry,
        "task_vulnerability": task_vuln,
        "quant_concurrency_interaction": interaction_qc,
        "backend_quant_decomposition": backend_quant,
        "jailbreak_synthesis": jailbreak_synth,
        "family_patterns": family_patterns,
        "heterogeneity": heterogeneity,
        "deployment_matrix": deployment_matrix,
        "worst_cases": worst_cases,
        "power_analysis": power_agg,
        "bias_synthesis": bias_synthesis,
        "judge_synthesis": judge_synthesis,
        "correlation": correlation,
        "decomposition": decomposition,
        "outlier_reports": outlier_reports,
        "headlines": headlines,
    }


# ---------------------------------------------------------------------------
# Pass implementations
# ---------------------------------------------------------------------------


def _pass_cross_validation(
    tr134: dict, tr135: dict, tr136: dict, available: dict
) -> dict[str, Any]:
    """Pass 2: Cross-TR baseline validation."""
    cross_validation: dict[str, Any] = {}

    for base_model, names in SHARED_MODELS.items():
        model_cv: dict[str, Any] = {"model": base_model, "per_task": {}}
        for task in sorted(SAFETY_TASKS | CAPABILITY_TASKS):
            scores: dict[str, float | None] = {}
            if available["tr134"]:
                scores["tr134"] = _tr134_score(
                    tr134.get("group_stats", {}), names["tr134"], ANCHOR_QUANT, task
                )
            if available["tr135"]:
                scores["tr135"] = _tr135_score(
                    tr135.get("group_stats", {}), names["tr135"], ANCHOR_N, task
                )
            if available["tr136"]:
                scores["tr136"] = _tr136_score(
                    tr136.get("group_stats", {}), names["tr136"], ANCHOR_BACKEND, task
                )

            valid = {k: v for k, v in scores.items() if v is not None}
            if len(valid) >= 2:
                vals = list(valid.values())
                max_delta = max(vals) - min(vals)
                model_cv["per_task"][task] = {
                    "scores": {k: round(v, 4) for k, v in valid.items()},
                    "max_delta_pp": round(max_delta * 100, 2),
                    "consistent": max_delta * 100 <= BASELINE_TOLERANCE_PP,
                }
            else:
                model_cv["per_task"][task] = {
                    "scores": {k: round(v, 4) for k, v in valid.items()},
                    "max_delta_pp": None,
                    "consistent": None,
                }

        # Aggregate per model
        deltas = [
            t["max_delta_pp"]
            for t in model_cv["per_task"].values()
            if t["max_delta_pp"] is not None
        ]
        model_cv["mean_delta_pp"] = round(_mean(deltas), 2) if deltas else None
        model_cv["all_consistent"] = all(
            t.get("consistent", True)
            for t in model_cv["per_task"].values()
            if t.get("consistent") is not None
        )
        n_inconsistent = sum(
            1 for t in model_cv["per_task"].values() if t.get("consistent") is False
        )
        model_cv["n_inconsistent_tasks"] = n_inconsistent
        cross_validation[base_model] = model_cv

    return cross_validation


def _pass_effect_sizes(
    tr134: dict, tr135: dict, tr136: dict, available: dict
) -> dict[str, Any]:
    """Pass 3: Effect size ranking."""
    effect_sizes: dict[str, Any] = {}

    for base_model, names in SHARED_MODELS.items():
        model_effects: dict[str, Any] = {"model": base_model}

        # Quantization effect (TR134): baseline -> Q2_K
        if available["tr134"]:
            gs134 = tr134.get("group_stats", {})
            baseline_q = "FP16"
            baseline_scores = []
            worst_scores = []
            baseline_n_total = 0
            worst_n_total = 0
            for task in SAFETY_TASKS:
                bs = _tr134_score(gs134, names["tr134"], baseline_q, task)
                if bs is None:
                    bs = _tr134_score(gs134, names["tr134"], "Q8_0", task)
                    if bs is not None:
                        baseline_q = "Q8_0"
                ws = _tr134_score(gs134, names["tr134"], "Q2_K", task)
                if bs is not None:
                    baseline_scores.append(bs)
                    baseline_n_total += _tr134_n(
                        gs134, names["tr134"], baseline_q, task
                    )
                if ws is not None:
                    worst_scores.append(ws)
                    worst_n_total += _tr134_n(gs134, names["tr134"], "Q2_K", task)

            if baseline_scores and worst_scores:
                quant_delta = _mean(baseline_scores) - _mean(worst_scores)
                b_std = _std(baseline_scores) if len(baseline_scores) > 1 else 0.0
                w_std = _std(worst_scores) if len(worst_scores) > 1 else 0.0
                model_effects["quant"] = {
                    "baseline_quant": baseline_q,
                    "worst_quant": "Q2_K",
                    "baseline_safety": round(_mean(baseline_scores), 4),
                    "worst_safety": round(_mean(worst_scores), 4),
                    "delta_pp": round(quant_delta * 100, 2),
                    "direction": "degradation" if quant_delta > 0 else "improvement",
                    "baseline_std": round(b_std, 4),
                    "worst_std": round(w_std, 4),
                    "baseline_n": baseline_n_total,
                    "worst_n": worst_n_total,
                    "cohens_d": round(
                        _cohens_d(
                            _mean(baseline_scores),
                            b_std,
                            len(baseline_scores),
                            _mean(worst_scores),
                            w_std,
                            len(worst_scores),
                        ),
                        4,
                    ),
                }

        # Concurrency effect (TR135): N=1 -> N=max
        if available["tr135"]:
            gs135 = tr135.get("group_stats", {})
            n_levels = tr135.get("metadata", {}).get("n_levels", [1, 2, 4, 8])
            max_n = max(n_levels) if n_levels else 8
            n1_scores = []
            n_max_scores = []
            for task in SAFETY_TASKS:
                s1 = _tr135_score(gs135, names["tr135"], 1, task)
                s_max = _tr135_score(gs135, names["tr135"], max_n, task)
                if s1 is not None:
                    n1_scores.append(s1)
                if s_max is not None:
                    n_max_scores.append(s_max)

            if n1_scores and n_max_scores:
                conc_delta = _mean(n1_scores) - _mean(n_max_scores)
                model_effects["concurrency"] = {
                    "n1_safety": round(_mean(n1_scores), 4),
                    "n_max_safety": round(_mean(n_max_scores), 4),
                    "max_n": max_n,
                    "delta_pp": round(conc_delta * 100, 2),
                    "direction": "degradation" if conc_delta > 0 else "improvement",
                }

        # Backend effect (TR136): max - min across backends
        if available["tr136"]:
            gs136 = tr136.get("group_stats", {})
            backends = tr136.get("metadata", {}).get("backends", [])
            backend_means: dict[str, list[float]] = defaultdict(list)
            for task in SAFETY_TASKS:
                for b in backends:
                    s = _tr136_score(gs136, names["tr136"], b, task)
                    if s is not None:
                        backend_means[b].append(s)

            if backend_means:
                b_avgs = {
                    b: _mean(scores) for b, scores in backend_means.items() if scores
                }
                if len(b_avgs) >= 2:
                    best_b = max(b_avgs, key=b_avgs.get)  # type: ignore[arg-type]
                    worst_b = min(b_avgs, key=b_avgs.get)  # type: ignore[arg-type]
                    backend_delta = b_avgs[best_b] - b_avgs[worst_b]
                    model_effects["backend"] = {
                        "best_backend": best_b,
                        "best_safety": round(b_avgs[best_b], 4),
                        "worst_backend": worst_b,
                        "worst_safety": round(b_avgs[worst_b], 4),
                        "delta_pp": round(backend_delta * 100, 2),
                        "per_backend": {b: round(v, 4) for b, v in b_avgs.items()},
                    }

        # Rank axes by delta
        axes = []
        for axis in ("quant", "concurrency", "backend"):
            if axis in model_effects:
                axes.append((axis, abs(model_effects[axis]["delta_pp"])))
        axes.sort(key=lambda x: x[1], reverse=True)
        model_effects["ranking"] = [{"axis": a, "abs_delta_pp": d} for a, d in axes]

        effect_sizes[base_model] = model_effects

    # Aggregate ranking across models
    axis_totals: dict[str, list[float]] = defaultdict(list)
    for me in effect_sizes.values():
        if not isinstance(me, dict) or "model" not in me:
            continue
        for axis in ("quant", "concurrency", "backend"):
            if axis in me:
                axis_totals[axis].append(abs(me[axis]["delta_pp"]))
    aggregate_ranking = sorted(
        [
            {"axis": a, "mean_delta_pp": round(_mean(ds), 2), "n_models": len(ds)}
            for a, ds in axis_totals.items()
        ],
        key=lambda x: x["mean_delta_pp"],
        reverse=True,
    )
    effect_sizes["_aggregate_ranking"] = aggregate_ranking

    return effect_sizes


def _pass_asymmetry(
    tr134: dict, tr135: dict, tr136: dict, available: dict
) -> dict[str, Any]:
    """Pass 4: Safety-capability asymmetry."""
    asymmetry: dict[str, Any] = {}

    if available["tr134"]:
        sc134 = tr134.get("slope_comparisons", {})
        for model, data in sc134.items():
            key = f"tr134__{model}"
            safety_slope = data.get("avg_safety_slope", 0)
            cap_slope = data.get("avg_capability_slope", 0)
            asymmetry[key] = {
                "axis": "quantization",
                "model": model,
                "family": infer_family(model),
                "safety_slope": safety_slope,
                "capability_slope": cap_slope,
                "divergence": data.get("divergence", 0),
                "safety_degrades_faster": data.get("safety_degrades_faster", False),
                "ci_overlap": data.get("ci_overlap"),
                "conclusion": data.get("conclusion", ""),
            }

    if available["tr135"]:
        div135 = tr135.get("safety_capability_divergence", {})
        for model, data in div135.items():
            key = f"tr135__{model}"
            asymmetry[key] = {
                "axis": "concurrency",
                "model": model,
                "family": infer_family(model),
                "safety_slope": data.get("safety_slope", 0),
                "capability_slope": data.get("capability_slope", 0),
                "slope_difference": data.get("slope_difference", 0),
                "interpretation": data.get("interpretation", "unknown"),
                "safety_degrades_faster": data.get("safety_slope", 0)
                > data.get("capability_slope", 0),
            }

    if available["tr136"]:
        gs136 = tr136.get("group_stats", {})
        models136 = tr136.get("metadata", {}).get("models", [])
        backends136 = tr136.get("metadata", {}).get("backends", [])
        for model in models136:
            safety_vars = []
            cap_vars = []
            for b in backends136:
                s_scores = [_tr136_score(gs136, model, b, t) for t in SAFETY_TASKS]
                c_scores = [_tr136_score(gs136, model, b, t) for t in CAPABILITY_TASKS]
                s_valid = [s for s in s_scores if s is not None]
                c_valid = [c for c in c_scores if c is not None]
                if s_valid:
                    safety_vars.append(_mean(s_valid))
                if c_valid:
                    cap_vars.append(_mean(c_valid))

            if len(safety_vars) >= 2 and len(cap_vars) >= 2:
                safety_range = max(safety_vars) - min(safety_vars)
                cap_range = max(cap_vars) - min(cap_vars)
                key = f"tr136__{model}"
                asymmetry[key] = {
                    "axis": "backend",
                    "model": model,
                    "family": infer_family(model),
                    "safety_range_pp": round(safety_range * 100, 2),
                    "capability_range_pp": round(cap_range * 100, 2),
                    "safety_more_variable": safety_range > cap_range,
                    "ratio": (
                        round(safety_range / cap_range, 3) if cap_range > 1e-6 else None
                    ),
                    "safety_degrades_faster": safety_range > cap_range,
                }

    # Summary: count by axis
    axis_summary: dict[str, dict] = {}
    for axis_name in ("quantization", "concurrency", "backend"):
        entries = [
            v
            for v in asymmetry.values()
            if isinstance(v, dict) and v.get("axis") == axis_name
        ]
        n_faster = sum(1 for e in entries if e.get("safety_degrades_faster"))
        axis_summary[axis_name] = {
            "n_models": len(entries),
            "n_safety_faster": n_faster,
            "pct_safety_faster": (
                round(n_faster / len(entries) * 100, 1) if entries else 0
            ),
        }
    asymmetry["_axis_summary"] = axis_summary

    return asymmetry


def _pass_task_vulnerability(
    tr134: dict, tr135: dict, tr136: dict, available: dict
) -> dict[str, dict[str, Any]]:
    """Pass 5: Per-task vulnerability matrix."""
    task_vuln: dict[str, dict[str, Any]] = {}

    for task in sorted(SAFETY_TASKS | CAPABILITY_TASKS):
        task_entry: dict[str, Any] = {"task": task}
        domain = "capability" if task in CAPABILITY_TASKS else "safety"

        # Quant vulnerability (TR134): average slope across models
        if available["tr134"]:
            slopes134 = tr134.get("degradation_slopes", {})
            metric = TASK_METRIC.get(task)
            task_slopes = []
            if metric:
                for key, val in slopes134.items():
                    if key.endswith(f"|{domain}|{metric}"):
                        task_slopes.append(val.get("slope", 0))
            if task_slopes:
                task_entry["quant_mean_slope"] = round(_mean(task_slopes), 6)
                task_entry["quant_mean_abs_slope"] = round(
                    _mean([abs(s) for s in task_slopes]), 6
                )
                task_entry["quant_n_models"] = len(task_slopes)

        # Concurrency vulnerability (TR135)
        if available["tr135"]:
            slopes135 = tr135.get("safety_slopes", {})
            task_slopes = []
            for model, model_data in slopes135.items():
                if isinstance(model_data, dict) and task in model_data:
                    ts = model_data[task]
                    if isinstance(ts, dict):
                        task_slopes.append(ts.get("slope", 0))
            if task_slopes:
                task_entry["concurrency_mean_slope"] = round(_mean(task_slopes), 6)
                task_entry["concurrency_mean_abs_slope"] = round(
                    _mean([abs(s) for s in task_slopes]), 6
                )
                task_entry["concurrency_n_models"] = len(task_slopes)

        # Backend vulnerability (TR136): chi-squared p
        if available["tr136"]:
            chi136 = tr136.get("per_task_chi_squared", {})
            chi_vals = []
            for key, val in chi136.items():
                if key.endswith(f"__{task}") and isinstance(val, dict):
                    p = val.get("p_value")
                    if p is not None:
                        chi_vals.append(p)
            if chi_vals:
                task_entry["backend_min_chi_p"] = round(min(chi_vals), 6)
                task_entry["backend_significant"] = min(chi_vals) < 0.05
                task_entry["backend_n_models"] = len(chi_vals)

        # Most vulnerable axis for this task
        axis_effects = {}
        if "quant_mean_abs_slope" in task_entry:
            axis_effects["quant"] = task_entry["quant_mean_abs_slope"]
        if "concurrency_mean_abs_slope" in task_entry:
            axis_effects["concurrency"] = task_entry["concurrency_mean_abs_slope"]
        if axis_effects:
            task_entry["most_vulnerable_axis"] = max(axis_effects, key=axis_effects.get)  # type: ignore[arg-type]

        task_vuln[task] = task_entry

    return task_vuln


def _pass_qc_interaction(tr134: dict, tr135: dict, available: dict) -> dict[str, Any]:
    """Pass 6: Quant x concurrency projection."""
    interaction_qc: dict[str, Any] = {}

    if not (available.get("tr134") and available.get("tr135")):
        return interaction_qc

    gs134 = tr134.get("group_stats", {})
    gs135 = tr135.get("group_stats", {})

    for base_model, names in SHARED_MODELS.items():
        quant_deltas = []
        conc_deltas = []
        for task in SAFETY_TASKS:
            fp16 = _tr134_score(gs134, names["tr134"], "FP16", task)
            q4 = _tr134_score(gs134, names["tr134"], ANCHOR_QUANT, task)
            n1 = _tr135_score(gs135, names["tr135"], 1, task)
            n8 = _tr135_score(gs135, names["tr135"], 8, task)

            if fp16 is not None and q4 is not None:
                quant_deltas.append(fp16 - q4)
            elif q4 is None:
                q8 = _tr134_score(gs134, names["tr134"], "Q8_0", task)
                if q8 is not None and fp16 is not None:
                    quant_deltas.append(fp16 - q8)
            if n1 is not None and n8 is not None:
                conc_deltas.append(n1 - n8)

        if quant_deltas and conc_deltas:
            q_marginal = _mean(quant_deltas)
            c_marginal = _mean(conc_deltas)
            combined_additive = q_marginal + c_marginal

            interaction_qc[base_model] = {
                "quant_marginal_pp": round(q_marginal * 100, 2),
                "concurrency_marginal_pp": round(c_marginal * 100, 2),
                "additive_projection_pp": round(combined_additive * 100, 2),
                "quant_pct_of_total": (
                    round(
                        abs(q_marginal) / (abs(q_marginal) + abs(c_marginal)) * 100, 1
                    )
                    if abs(q_marginal) + abs(c_marginal) > 1e-6
                    else 50.0
                ),
                "note": (
                    "Additive model assumes no interaction. True interaction "
                    "requires factorial design (all quant x all N levels)."
                ),
            }

    return interaction_qc


def _pass_jailbreak_synthesis(
    tr134: dict, tr135: dict, available: dict
) -> dict[str, Any]:
    """Pass 8: Jailbreak synthesis across axes."""
    jailbreak_synth: dict[str, Any] = {}

    if available.get("tr134"):
        ja134 = tr134.get("jailbreak_amplification", {})
        if ja134.get("available"):
            slopes = ja134.get("jailbreak_slopes", {})
            # Find most/least vulnerable jailbreak type
            if slopes:
                sorted_types = sorted(slopes.items(), key=lambda x: x[1])
                jailbreak_synth["quant_axis"] = {
                    "source": "tr134",
                    "n_total": ja134.get("n_total", 0),
                    "success_rates": ja134.get("success_rates", {}),
                    "slopes": slopes,
                    "per_category": ja134.get("per_category", {}),
                    "most_effective_type": sorted_types[0][0] if sorted_types else None,
                    "least_effective_type": (
                        sorted_types[-1][0] if sorted_types else None
                    ),
                }

    if available.get("tr135"):
        jb135 = tr135.get("jailbreak_breakdown", {})
        if jb135:
            jailbreak_synth["concurrency_axis"] = {
                "source": "tr135",
                "per_model": {},
            }
            for model, data in jb135.items():
                if isinstance(data, dict):
                    jailbreak_synth["concurrency_axis"]["per_model"][model] = data

    return jailbreak_synth


def _pass_family_patterns(
    tr134: dict, available: dict, effect_sizes: dict
) -> dict[str, Any]:
    """Pass 9: Family-level patterns."""
    family_patterns: dict[str, Any] = {}

    if available.get("tr134"):
        fc134 = tr134.get("family_comparison", {})
        if fc134.get("available"):
            family_patterns["quant_axis"] = {
                "f_statistic": fc134.get("f_statistic"),
                "p_value": fc134.get("p_value"),
                "significant": fc134.get("significant"),
                "conclusion": fc134.get("conclusion"),
                "per_family": fc134.get("per_family", {}),
            }

    # Cross-axis family comparison using shared models
    family_effects: dict[str, dict[str, float]] = defaultdict(dict)
    for base_model, me in effect_sizes.items():
        if not isinstance(me, dict) or "model" not in me:
            continue
        family = infer_family(base_model)
        for axis in ("quant", "concurrency", "backend"):
            if axis in me:
                family_effects[family][f"{axis}_{base_model}"] = me[axis]["delta_pp"]

    family_patterns["cross_axis"] = dict(family_effects)

    return family_patterns


def _pass_heterogeneity(effect_sizes: dict) -> dict[str, Any]:
    """Pass 10: Model-axis heterogeneity (I-squared)."""
    heterogeneity: dict[str, Any] = {}

    for axis in ("quant", "concurrency", "backend"):
        effects_list = []
        model_names = []
        for base_model, me in effect_sizes.items():
            if not isinstance(me, dict) or "model" not in me:
                continue
            if axis in me:
                effects_list.append(me[axis]["delta_pp"])
                model_names.append(base_model)

        if len(effects_list) >= 2:
            i2 = _i_squared(effects_list)
            heterogeneity[axis] = {
                "effects": effects_list,
                "models": model_names,
                "n_models": len(effects_list),
                "mean_effect_pp": round(_mean(effects_list), 2),
                "std_effect_pp": round(_std(effects_list), 2),
                "min_effect_pp": round(min(effects_list), 2),
                "max_effect_pp": round(max(effects_list), 2),
                "range_pp": round(max(effects_list) - min(effects_list), 2),
                "i_squared": round(i2, 1),
                "interpretation": (
                    "low" if i2 < 25 else "moderate" if i2 < 75 else "high"
                ),
            }

    return heterogeneity


def _pass_deployment_matrix(
    tr134: dict, tr135: dict, tr136: dict, available: dict, effect_sizes: dict
) -> list[dict]:
    """Pass 11: Safety-adjusted deployment matrix."""
    deployment_matrix: list[dict] = []
    quant_levels = ["FP16", "Q8_0", "Q4_K_M", "Q2_K"]
    n_levels = [1, 4, 8]

    if not (available.get("tr134") and available.get("tr135")):
        return deployment_matrix

    gs134 = tr134.get("group_stats", {})
    gs135 = tr135.get("group_stats", {})

    for base_model, names in SHARED_MODELS.items():
        # Get FP16/N=1 baseline safety
        baseline_scores = []
        for task in SAFETY_TASKS:
            bs = _tr134_score(gs134, names["tr134"], "FP16", task)
            if bs is None:
                bs = _tr134_score(gs134, names["tr134"], "Q8_0", task)
            if bs is not None:
                baseline_scores.append(bs)
        if not baseline_scores:
            continue
        baseline = _mean(baseline_scores)

        # Quant marginal effects
        quant_effects: dict[str, float] = {}
        for q in quant_levels:
            q_scores = []
            for task in SAFETY_TASKS:
                s = _tr134_score(gs134, names["tr134"], q, task)
                if s is not None:
                    q_scores.append(s)
            if q_scores:
                quant_effects[q] = baseline - _mean(q_scores)

        # Concurrency marginal effects
        conc_effects: dict[int, float] = {}
        n1_scores = []
        for task in SAFETY_TASKS:
            s = _tr135_score(gs135, names["tr135"], 1, task)
            if s is not None:
                n1_scores.append(s)
        n1_mean = _mean(n1_scores) if n1_scores else baseline

        for n in n_levels:
            n_scores = []
            for task in SAFETY_TASKS:
                s = _tr135_score(gs135, names["tr135"], n, task)
                if s is not None:
                    n_scores.append(s)
            if n_scores:
                conc_effects[n] = n1_mean - _mean(n_scores)

        # Backend marginal effect
        backend_effect = 0.0
        if available.get("tr136") and base_model in effect_sizes:
            be = effect_sizes[base_model].get("backend", {})
            backend_effect = be.get("delta_pp", 0) / 100.0

        for q in quant_levels:
            for n in n_levels:
                q_loss = quant_effects.get(q, 0)
                c_loss = conc_effects.get(n, 0)
                projected = baseline - q_loss - c_loss
                retention = projected / baseline * 100 if baseline > 0 else 0

                deployment_matrix.append(
                    {
                        "model": base_model,
                        "quant": q,
                        "n_agents": n,
                        "baseline_safety": round(baseline, 4),
                        "quant_cost_pp": round(q_loss * 100, 2),
                        "concurrency_cost_pp": round(c_loss * 100, 2),
                        "backend_range_pp": round(backend_effect * 100, 2),
                        "total_cost_pp": round((q_loss + c_loss) * 100, 2),
                        "projected_safety": round(projected, 4),
                        "retention_pct": round(retention, 1),
                        "risk_level": classify_risk(retention),
                    }
                )

    # Sort by risk
    risk_order = {"critical": 0, "high": 1, "moderate": 2, "low": 3}
    deployment_matrix.sort(
        key=lambda x: (risk_order.get(x["risk_level"], 9), -x.get("retention_pct", 0))
    )

    return deployment_matrix


def _pass_worst_cases(
    effect_sizes: dict, deployment_matrix: list[dict]
) -> dict[str, Any]:
    """Pass 12: Worst-case identification."""
    worst_cases: dict[str, Any] = {}

    for axis in ("quant", "concurrency", "backend"):
        worst = None
        for base_model, me in effect_sizes.items():
            if not isinstance(me, dict) or "model" not in me:
                continue
            if axis in me:
                d = abs(me[axis]["delta_pp"])
                if worst is None or d > worst["delta_pp"]:
                    worst = {
                        "model": base_model,
                        "delta_pp": d,
                        **me[axis],
                    }
        if worst:
            worst_cases[axis] = worst

    # Combined worst from deployment matrix
    if deployment_matrix:
        worst_config = deployment_matrix[0]  # already sorted by risk
        worst_cases["combined_worst"] = worst_config

    # Maximum total safety cost
    max_total = 0.0
    for row in deployment_matrix:
        total = row.get("total_cost_pp", 0)
        if total > max_total:
            max_total = total
    worst_cases["max_total_cost_pp"] = round(max_total, 2)

    # Count by risk level
    risk_counts = defaultdict(int)
    for row in deployment_matrix:
        risk_counts[row["risk_level"]] += 1
    worst_cases["risk_level_counts"] = dict(risk_counts)

    return worst_cases


def _pass_power_analysis(
    tr134: dict, tr135: dict, tr136: dict, available: dict
) -> dict[str, Any]:
    """Pass 13: Aggregate power and sensitivity."""
    power_agg: dict[str, Any] = {}

    if available.get("tr134"):
        pa134 = tr134.get("power_analysis", {})
        power_agg["tr134"] = {
            "mde_safety_pp": pa134.get("mde_safety_pp"),
            "mde_capability_pp": pa134.get("mde_capability_pp"),
            "mde_cohens_d": pa134.get("mde_cohens_d"),
            "avg_n_per_variant": pa134.get("avg_safety_n_per_variant"),
            "interpretation": pa134.get("interpretation", ""),
        }

    if available.get("tr135"):
        pa135 = tr135.get("power_analysis", {})
        tr135_mdes = []
        per_model = {}
        for model, data in pa135.items():
            if isinstance(data, dict) and data.get("mde_safety_pp") is not None:
                tr135_mdes.append(data["mde_safety_pp"])
                per_model[model] = {
                    "mde_safety_pp": data.get("mde_safety_pp"),
                    "avg_n": data.get("avg_n_per_variant"),
                }
        power_agg["tr135"] = {
            "mean_mde_safety_pp": round(_mean(tr135_mdes), 1) if tr135_mdes else None,
            "per_model": per_model,
        }

    if available.get("tr136"):
        pa136 = tr136.get("power_analysis", {})
        tr136_mdes = []
        per_model = {}
        for model, data in pa136.items():
            if isinstance(data, dict) and data.get("mde_safety_pp") is not None:
                tr136_mdes.append(data["mde_safety_pp"])
                per_model[model] = {
                    "mde_safety_pp": data.get("mde_safety_pp"),
                    "avg_n": data.get("avg_n_per_variant"),
                }
        power_agg["tr136"] = {
            "mean_mde_safety_pp": round(_mean(tr136_mdes), 1) if tr136_mdes else None,
            "per_model": per_model,
        }

    # Sensitivity: what's the smallest effect we'd catch across all TRs?
    all_mdes = []
    for src, data in power_agg.items():
        if isinstance(data, dict):
            m = data.get("mde_safety_pp") or data.get("mean_mde_safety_pp")
            if m is not None:
                all_mdes.append(m)
    power_agg["worst_mde_pp"] = max(all_mdes) if all_mdes else None
    power_agg["best_mde_pp"] = min(all_mdes) if all_mdes else None
    power_agg["program_sensitivity"] = (
        f"Effects >= {max(all_mdes):.1f}pp detectable across all TRs"
        if all_mdes
        else "Insufficient data"
    )

    return power_agg


def _pass_bias_synthesis(
    tr134: dict, tr135: dict, tr136: dict, available: dict
) -> dict[str, Any]:
    """Pass 14: Per-category bias synthesis from BBQ across axes."""
    synthesis: dict[str, Any] = {"available": False}

    # TR134 per-category bias (most detailed)
    if available.get("tr134"):
        pcb = tr134.get("per_category_bias", {})
        if pcb:
            synthesis["available"] = True
            synthesis["quant_axis"] = {
                "ranked_categories": pcb.get("ranked_categories", []),
                "most_vulnerable": pcb.get("most_vulnerable"),
                "least_vulnerable": pcb.get("least_vulnerable"),
                "category_slopes": pcb.get("category_slopes", {}),
            }

    # TR135 may have bias per N-level
    if available.get("tr135"):
        gs135 = tr135.get("group_stats", {})
        # Check if any bias data exists
        bias_keys = [k for k in gs135 if "bbq_bias" in k]
        if bias_keys:
            synthesis["concurrency_axis_available"] = True
            synthesis["concurrency_n_bias_groups"] = len(bias_keys)

    # TR136 bias across backends
    if available.get("tr136"):
        gs136 = tr136.get("group_stats", {})
        bias_keys = [k for k in gs136 if "bbq_bias" in k]
        if bias_keys:
            synthesis["backend_axis_available"] = True
            synthesis["backend_n_bias_groups"] = len(bias_keys)

    return synthesis


def _pass_judge_synthesis(
    tr134: dict, tr135: dict, tr136: dict, available: dict
) -> dict[str, Any]:
    """Pass 15: Judge agreement synthesis across axes."""
    synthesis: dict[str, Any] = {"available": False}

    if available.get("tr134"):
        ja = tr134.get("judge_agreement", {})
        if ja.get("available"):
            synthesis["available"] = True
            per_task = ja.get("per_task", {})
            # Compute overall kappa as mean of per-task kappas
            kappas = [
                v.get("kappa")
                for v in per_task.values()
                if isinstance(v, dict) and v.get("kappa") is not None
            ]
            overall_kappa = round(_mean(kappas), 4) if kappas else None
            synthesis["quant_axis"] = {
                "n_judged": ja.get("n_judged", 0),
                "overall_kappa": overall_kappa,
                "per_task_kappa": {
                    k: {
                        "kappa": v.get("kappa"),
                        "agreement_pct": v.get("agreement_pct"),
                    }
                    for k, v in per_task.items()
                    if isinstance(v, dict)
                },
                "per_quant_kappa": ja.get("per_task_per_quant", {}),
            }

    if available.get("tr135"):
        ja = tr135.get("judge_agreement", {})
        if ja.get("available"):
            synthesis["available"] = True
            synthesis["concurrency_axis"] = {
                "n_judged": ja.get("n_judged", 0),
                "overall_kappa": ja.get("overall_kappa"),
                "per_n_kappa": ja.get("per_n_kappa", {}),
            }

    if available.get("tr136"):
        ja = tr136.get("judge_agreement", {})
        if ja.get("available"):
            synthesis["available"] = True
            synthesis["backend_axis"] = {
                "n_judged": ja.get("n_judged", 0),
                "overall_kappa": ja.get("overall_kappa"),
                "per_backend_kappa": ja.get("per_backend_kappa", {}),
            }

    return synthesis


def _pass_bootstrap_effects(effect_sizes: dict) -> dict[str, Any]:
    """Pass 16: Bootstrap CI on cross-axis effect sizes."""
    effect_cis: dict[str, Any] = {}

    for axis in ("quant", "concurrency", "backend"):
        effects = []
        for base_model, me in effect_sizes.items():
            if not isinstance(me, dict) or "model" not in me:
                continue
            if axis in me:
                effects.append(me[axis]["delta_pp"])

        if len(effects) >= 2:
            ci = _bootstrap_ci(effects, n_boot=2000, seed=42)
            effect_cis[axis] = {
                **ci,
                "n_models": len(effects),
                "effects": effects,
            }

    return effect_cis


def _pass_cross_axis_correlation(effect_sizes: dict) -> dict[str, Any]:
    """Pass 17: Are models vulnerable on one axis also vulnerable on others?"""
    correlation: dict[str, Any] = {}

    # Collect per-model effects
    model_quant = {}
    model_conc = {}
    model_backend = {}
    for base_model, me in effect_sizes.items():
        if not isinstance(me, dict) or "model" not in me:
            continue
        if "quant" in me:
            model_quant[base_model] = abs(me["quant"]["delta_pp"])
        if "concurrency" in me:
            model_conc[base_model] = abs(me["concurrency"]["delta_pp"])
        if "backend" in me:
            model_backend[base_model] = abs(me["backend"]["delta_pp"])

    # Quant vs concurrency
    shared_qc = set(model_quant.keys()) & set(model_conc.keys())
    if len(shared_qc) >= 3:
        xs = [model_quant[m] for m in shared_qc]
        ys = [model_conc[m] for m in shared_qc]
        r = _pearson_r(xs, ys)
        correlation["quant_vs_concurrency"] = {
            "r": round(r, 4) if r is not None else None,
            "n_models": len(shared_qc),
            "models": sorted(shared_qc),
            "interpretation": (
                "strong positive"
                if r and r > 0.7
                else (
                    "moderate positive"
                    if r and r > 0.3
                    else (
                        "weak/no correlation"
                        if r and r > -0.3
                        else "negative" if r else "insufficient data"
                    )
                )
            ),
        }

    # Quant vs backend
    shared_qb = set(model_quant.keys()) & set(model_backend.keys())
    if len(shared_qb) >= 3:
        xs = [model_quant[m] for m in shared_qb]
        ys = [model_backend[m] for m in shared_qb]
        r = _pearson_r(xs, ys)
        correlation["quant_vs_backend"] = {
            "r": round(r, 4) if r is not None else None,
            "n_models": len(shared_qb),
            "models": sorted(shared_qb),
        }

    # Concurrency vs backend
    shared_cb = set(model_conc.keys()) & set(model_backend.keys())
    if len(shared_cb) >= 3:
        xs = [model_conc[m] for m in shared_cb]
        ys = [model_backend[m] for m in shared_cb]
        r = _pearson_r(xs, ys)
        correlation["concurrency_vs_backend"] = {
            "r": round(r, 4) if r is not None else None,
            "n_models": len(shared_cb),
            "models": sorted(shared_cb),
        }

    correlation["sufficient_data"] = any(
        v.get("r") is not None for v in correlation.values() if isinstance(v, dict)
    )

    return correlation


def _pass_effect_decomposition(effect_sizes: dict) -> dict[str, Any]:
    """Pass 18: What % of total safety cost comes from each axis?"""
    decomposition: dict[str, Any] = {}

    # Per-model decomposition
    for base_model, me in effect_sizes.items():
        if not isinstance(me, dict) or "model" not in me:
            continue
        axis_costs = {}
        for axis in ("quant", "concurrency", "backend"):
            if axis in me:
                axis_costs[axis] = abs(me[axis]["delta_pp"])

        total = sum(axis_costs.values())
        if total > 0:
            decomposition[base_model] = {
                "model": base_model,
                "total_pp": round(total, 2),
                "per_axis": {
                    a: {
                        "abs_delta_pp": round(v, 2),
                        "pct_of_total": round(v / total * 100, 1),
                    }
                    for a, v in axis_costs.items()
                },
                "dominant_axis": max(axis_costs, key=axis_costs.get),  # type: ignore[arg-type]
            }

    # Aggregate decomposition
    agg_costs: dict[str, list[float]] = defaultdict(list)
    for m, d in decomposition.items():
        if isinstance(d, dict) and "per_axis" in d:
            for axis, data in d["per_axis"].items():
                agg_costs[axis].append(data["pct_of_total"])

    if agg_costs:
        decomposition["_aggregate"] = {
            axis: {
                "mean_pct": round(_mean(pcts), 1),
                "n_models": len(pcts),
            }
            for axis, pcts in agg_costs.items()
        }

    return decomposition


def _compute_headlines(
    effect_sizes: dict,
    asymmetry: dict,
    deployment_matrix: list[dict],
    worst_cases: dict,
    total_samples: int,
    n_sources: int,
    correlation: dict,
) -> dict[str, Any]:
    """Compute executive summary headline numbers."""
    headlines: dict[str, Any] = {}

    agg = effect_sizes.get("_aggregate_ranking", [])
    if agg:
        headlines["most_dangerous_axis"] = agg[0]["axis"]
        headlines["most_dangerous_delta_pp"] = agg[0]["mean_delta_pp"]
    headlines["max_total_cost_pp"] = worst_cases.get("max_total_cost_pp", 0)

    risk_counts = worst_cases.get("risk_level_counts", {})
    headlines["n_critical_configs"] = risk_counts.get("critical", 0)
    headlines["n_high_risk_configs"] = risk_counts.get("critical", 0) + risk_counts.get(
        "high", 0
    )
    headlines["n_total_configs"] = len(deployment_matrix)
    headlines["total_samples"] = total_samples
    headlines["n_sources"] = n_sources

    # Asymmetry headline
    asym_count = sum(
        1
        for v in asymmetry.values()
        if isinstance(v, dict) and v.get("safety_degrades_faster")
    )
    asym_total = sum(
        1 for v in asymmetry.values() if isinstance(v, dict) and "axis" in v
    )
    headlines["safety_degrades_faster_count"] = f"{asym_count}/{asym_total}"

    # Cross-axis correlation
    if correlation.get("sufficient_data"):
        for pair, data in correlation.items():
            if isinstance(data, dict) and "r" in data and data["r"] is not None:
                headlines["cross_axis_correlation"] = f"r={data['r']:.2f} ({pair})"
                break

    return headlines


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------


def write_deployment_csv(deployment_matrix: list[dict], output_path: Path) -> None:
    """Write deployment matrix to CSV."""
    if not deployment_matrix:
        return
    fieldnames = [
        "model",
        "quant",
        "n_agents",
        "baseline_safety",
        "quant_cost_pp",
        "concurrency_cost_pp",
        "total_cost_pp",
        "backend_range_pp",
        "projected_safety",
        "retention_pct",
        "risk_level",
    ]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(deployment_matrix)
    logger.info(
        "Wrote deployment CSV: %s (%d rows)", output_path, len(deployment_matrix)
    )


def write_effect_ranking_csv(effect_sizes: dict, output_path: Path) -> None:
    """Write effect size ranking to CSV."""
    rows = []
    for base_model, me in effect_sizes.items():
        if not isinstance(me, dict) or "model" not in me:
            continue
        row = {"model": base_model}
        for axis in ("quant", "concurrency", "backend"):
            if axis in me:
                row[f"{axis}_delta_pp"] = me[axis]["delta_pp"]
                row[f"{axis}_direction"] = me[axis].get("direction", "")
            else:
                row[f"{axis}_delta_pp"] = ""
                row[f"{axis}_direction"] = ""
        ranking = me.get("ranking", [])
        row["worst_axis"] = ranking[0]["axis"] if ranking else ""
        rows.append(row)

    if not rows:
        return
    fieldnames = [
        "model",
        "quant_delta_pp",
        "quant_direction",
        "concurrency_delta_pp",
        "concurrency_direction",
        "backend_delta_pp",
        "backend_direction",
        "worst_axis",
    ]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    logger.info("Wrote effect ranking CSV: %s (%d rows)", output_path, len(rows))


# ---------------------------------------------------------------------------
# Console summary
# ---------------------------------------------------------------------------


def print_summary(analysis: dict) -> None:
    """Print formatted console summary."""
    h = analysis.get("headlines", {})
    meta = analysis.get("metadata", {})

    print(f"\n{'='*70}")
    print("TR137: THE SAFETY TAX OF INFERENCE OPTIMIZATION")
    print(f"{'='*70}")
    print(
        f"  Sources: {meta.get('n_sources', 0)}/3 loaded | "
        f"{meta.get('total_samples_across_trs', 0):,} total samples"
    )

    warnings = meta.get("validation_warnings", [])
    if warnings:
        print(f"  Validation warnings: {len(warnings)}")
        for w in warnings[:3]:
            print(f"    - {w}")

    print(
        f"\n  Most dangerous axis: {h.get('most_dangerous_axis', 'N/A')} "
        f"(mean {h.get('most_dangerous_delta_pp', 0):.1f}pp)"
    )
    print(
        f"  Max combined cost:   {h.get('max_total_cost_pp', 0):.1f}pp "
        f"(quant + concurrency)"
    )
    print(
        f"  Critical configs:    {h.get('n_critical_configs', 0)}"
        f" / {h.get('n_total_configs', 0)} total"
    )
    print(f"  Safety > capability: {h.get('safety_degrades_faster_count', 'N/A')}")

    # Per-axis effect sizes
    es = analysis.get("effect_sizes", {})
    agg = es.get("_aggregate_ranking", [])
    if agg:
        print(f"\n  Effect size ranking:")
        for i, r in enumerate(agg, 1):
            print(
                f"    {i}. {r['axis']:15s} {r['mean_delta_pp']:+.1f}pp "
                f"(n={r['n_models']} models)"
            )

    # Cross-validation
    cv = analysis.get("cross_validation", {})
    n_inconsistent = sum(
        v.get("n_inconsistent_tasks", 0) for v in cv.values() if isinstance(v, dict)
    )
    if cv:
        print(
            f"\n  Cross-TR validation: {n_inconsistent} inconsistent task(s) "
            f"across {len(cv)} shared models"
        )

    # Heterogeneity
    het = analysis.get("heterogeneity", {})
    for axis, d in het.items():
        if isinstance(d, dict):
            print(
                f"  I-squared ({axis}): {d.get('i_squared', 0):.0f}% "
                f"({d.get('interpretation', 'N/A')})"
            )

    # Power
    pa = analysis.get("power_analysis", {})
    sensitivity = pa.get("program_sensitivity", "")
    if sensitivity:
        print(f"  Sensitivity: {sensitivity}")

    print(f"{'='*70}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="TR137 unified safety analysis")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--tr134-dir", type=Path, default=None)
    parser.add_argument("--tr135-dir", type=Path, default=None)
    parser.add_argument("--tr136-dir", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    analysis = analyze(args.tr134_dir, args.tr135_dir, args.tr136_dir)
    if not analysis:
        return 1

    out_dir = args.output_dir
    if out_dir is None:
        from datetime import UTC, datetime

        ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        out_dir = _REPO / "research" / "tr137" / "results" / ts
    out_dir.mkdir(parents=True, exist_ok=True)

    out_path = out_dir / "tr137_analysis.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(analysis, f, indent=2, default=str)
    logger.info("Wrote analysis to %s", out_path)

    # Write CSVs
    write_deployment_csv(
        analysis.get("deployment_matrix", []), out_dir / "tr137_deployment_matrix.csv"
    )
    write_effect_ranking_csv(
        analysis.get("effect_sizes", {}), out_dir / "tr137_effect_ranking.csv"
    )

    print_summary(analysis)

    return 0


if __name__ == "__main__":
    sys.exit(main())
