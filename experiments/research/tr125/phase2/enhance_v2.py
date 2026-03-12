#!/usr/bin/env python3
"""TR125 v2 Enhancement: Compute 10 missing analyses from existing raw data.

Reads samples.jsonl (24,990 rows) and phase2_analysis.json (8,653 lines),
computes Wilson CIs, MMLU/ARC differential, per-task generation quality,
all 7 metrics, outlier detection, Bonferroni correction, TOST equivalence,
TR123 cross-reference, full TTFT, and 29-variant enumeration.

Outputs: phase2_v2_enhancements.json
"""

from collections import defaultdict
import json
import math
from pathlib import Path

import numpy as np
from scipy import stats

# Paths
BASE = Path(__file__).resolve().parents[3]
DATA_DIR = BASE / "results" / "eval" / "tr125_phase2" / "20260221_120035"
SAMPLES_PATH = DATA_DIR / "samples.jsonl"
ANALYSIS_PATH = DATA_DIR / "phase2_analysis.json"
OUTPUT_PATH = DATA_DIR / "phase2_v2_enhancements.json"

QUANT_ORDER = ["FP16", "Q8_0", "Q6_K", "Q5_K_M", "Q4_K_M", "Q3_K_S", "Q2_K"]
MODEL_ORDER = ["llama3.2-1b", "qwen2.5-1.5b", "phi-2", "llama3.2-3b", "llama3.1-8b"]
GEN_TASKS = [
    "summarization",
    "qa",
    "code_generation",
    "creative_writing",
    "classification",
]
BENCH_TASKS = ["mmlu_real", "arc_challenge"]
KEY_METRICS = ["bertscore", "coherence", "rouge_l"]
ALL_METRICS = [
    "bertscore",
    "bleu",
    "coherence",
    "exact_match",
    "output_length",
    "repetition",
    "rouge_l",
]


def load_samples():
    """Load all 24,990 samples from JSONL."""
    samples = []
    with open(SAMPLES_PATH) as f:
        for line in f:
            samples.append(json.loads(line))
    print(f"Loaded {len(samples)} samples")
    return samples


def load_analysis():
    """Load the existing phase2_analysis.json."""
    with open(ANALYSIS_PATH) as f:
        return json.load(f)


def parse_model(model_name):
    """Extract base_model and quant_level from model name like 'llama3.2-1b-q4_K_M'."""
    # Handle FP16
    if model_name.endswith("-fp16"):
        return model_name[:-5], "FP16"
    # Find last hyphen before quant suffix
    for q in ["q8_0", "q6_K", "q5_K_M", "q4_K_M", "q3_K_S", "q2_K"]:
        if model_name.endswith(f"-{q}"):
            base = model_name[: -(len(q) + 1)]
            return base, q.upper().replace("Q", "Q")
    return model_name, "unknown"


# ─── Analysis 1: Wilson CIs for Benchmark Accuracy ───────────────────────────


def wilson_ci(p, n, z=1.96):
    """Wilson score interval for binomial proportion."""
    if n == 0:
        return (0.0, 0.0)
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    spread = z * math.sqrt((p * (1 - p) / n) + z**2 / (4 * n**2)) / denom
    return (max(0.0, center - spread), min(1.0, center + spread))


def compute_wilson_cis(analysis):
    """Compute Wilson CIs for all benchmark accuracy entries."""
    results = []
    for entry in analysis["benchmark_accuracy"]:
        p = entry["rescored_accuracy"]
        n = entry["n_samples"]
        ci_lower, ci_upper = wilson_ci(p, n)
        half_width = (ci_upper - ci_lower) / 2

        # Per-task CIs
        per_task_cis = {}
        for task_name, task_data in entry.get("per_task", {}).items():
            tp = task_data["rescored_acc"]
            tn = task_data["n"]
            tl, tu = wilson_ci(tp, tn)
            per_task_cis[task_name] = {
                "rescored_acc": tp,
                "n": tn,
                "ci_lower": round(tl, 4),
                "ci_upper": round(tu, 4),
                "ci_half_width_pp": round((tu - tl) / 2 * 100, 1),
            }

        results.append(
            {
                "base_model": entry["base_model"],
                "quant_level": entry["quant_level"],
                "rescored_accuracy": p,
                "n": n,
                "wilson_ci_lower": round(ci_lower, 4),
                "wilson_ci_upper": round(ci_upper, 4),
                "ci_half_width_pp": round(half_width * 100, 1),
                "per_task_cis": per_task_cis,
            }
        )
    return results


# ─── Analysis 2: MMLU vs ARC Differential ────────────────────────────────────


def compute_mmlu_arc_differential(analysis):
    """Compute per-variant MMLU vs ARC rescored accuracy differential."""
    results = []
    for entry in analysis["benchmark_accuracy"]:
        pt = entry.get("per_task", {})
        mmlu = pt.get("mmlu_real", {})
        arc = pt.get("arc_challenge", {})
        if mmlu and arc:
            mmlu_acc = mmlu["rescored_acc"]
            arc_acc = arc["rescored_acc"]
            diff = round((mmlu_acc - arc_acc) * 100, 1)  # pp
            results.append(
                {
                    "base_model": entry["base_model"],
                    "quant_level": entry["quant_level"],
                    "mmlu_rescored": round(mmlu_acc * 100, 1),
                    "arc_rescored": round(arc_acc * 100, 1),
                    "mmlu_minus_arc_pp": diff,
                    "mmlu_n": mmlu["n"],
                    "arc_n": arc["n"],
                }
            )
    return results


# ─── Analysis 3: Per-Task Generation Quality Breakdown ───────────────────────


def compute_per_task_generation(samples):
    """Compute per-task generation quality for 5 gen tasks × 34 variants."""
    gen_samples = [s for s in samples if s["task_name"] in GEN_TASKS]
    print(f"  Generation samples: {len(gen_samples)}")

    # Group by (model, task)
    groups = defaultdict(list)
    for s in gen_samples:
        base, quant = parse_model(s["model"])
        groups[(base, quant, s["task_name"])].append(s)

    results = []
    for (base, quant, task), task_samples in sorted(groups.items()):
        entry = {
            "base_model": base,
            "quant_level": quant,
            "task": task,
            "n": len(task_samples),
        }
        for metric in KEY_METRICS:
            values = []
            for s in task_samples:
                if metric in s.get("metrics", {}):
                    v = s["metrics"][metric]
                    score = v.get("score", v) if isinstance(v, dict) else v
                    if score is not None and not (
                        isinstance(score, float) and math.isnan(score)
                    ):
                        values.append(float(score))
            if values:
                arr = np.array(values)
                entry[f"{metric}_mean"] = round(float(np.mean(arr)), 4)
                entry[f"{metric}_std"] = (
                    round(float(np.std(arr, ddof=1)), 4) if len(arr) > 1 else 0.0
                )
            else:
                entry[f"{metric}_mean"] = None
                entry[f"{metric}_std"] = None
        results.append(entry)
    return results


# ─── Analysis 4: All 7 Metrics (extract from quality_curves) ────────────────


def extract_all_7_metrics(analysis):
    """Extract all 7 generation metrics from quality_curves, including the 4 hidden ones."""
    results = []
    for entry in analysis["quality_curves"]:
        row = {
            "base_model": entry["base_model"],
            "quant_level": entry["quant_level"],
            "n_samples": entry["n_samples"],
        }
        for metric in ALL_METRICS:
            row[f"{metric}_mean"] = entry.get(f"{metric}_mean")
            row[f"{metric}_std"] = entry.get(f"{metric}_std")
            row[f"{metric}_ci_lower"] = entry.get(f"{metric}_ci_lower")
            row[f"{metric}_ci_upper"] = entry.get(f"{metric}_ci_upper")
            row[f"{metric}_delta_pct"] = entry.get(f"{metric}_delta_primary_pct")
        results.append(row)
    return results


# ─── Analysis 5: Outlier Detection on Timing Data ───────────────────────────


def detect_outliers_iqr(values, k=1.5):
    """IQR-based outlier detection."""
    arr = np.array(values)
    q1 = np.percentile(arr, 25)
    q3 = np.percentile(arr, 75)
    iqr = q3 - q1
    lower = q1 - k * iqr
    upper = q3 + k * iqr
    outlier_mask = (arr < lower) | (arr > upper)
    return {
        "n_total": len(arr),
        "n_outliers": int(np.sum(outlier_mask)),
        "outlier_pct": round(float(np.sum(outlier_mask)) / len(arr) * 100, 1),
        "q1": round(float(q1), 2),
        "q3": round(float(q3), 2),
        "iqr": round(float(iqr), 2),
        "lower_fence": round(float(lower), 2),
        "upper_fence": round(float(upper), 2),
    }


def compute_timing_outliers(samples):
    """Detect outliers in TTFT and decode timing per variant."""
    # Group by model
    groups = defaultdict(lambda: {"ttft": [], "decode": []})
    for s in samples:
        bm = s.get("backend_metadata", {})
        if bm:
            ttft = bm.get("ollama_prompt_eval_ms")
            decode = bm.get("ollama_eval_ms")
            if ttft is not None and ttft > 0:
                groups[s["model"]]["ttft"].append(ttft)
            if decode is not None and decode > 0:
                groups[s["model"]]["decode"].append(decode)

    results = []
    for model in sorted(groups.keys()):
        base, quant = parse_model(model)
        entry = {
            "base_model": base,
            "quant_level": quant,
            "model": model,
        }
        for metric_name in ["ttft", "decode"]:
            vals = groups[model][metric_name]
            if len(vals) >= 10:
                outlier_info = detect_outliers_iqr(vals)
                entry[f"{metric_name}_outliers"] = outlier_info
            else:
                entry[f"{metric_name}_outliers"] = {
                    "n_total": len(vals),
                    "n_outliers": 0,
                    "note": "insufficient samples",
                }
        results.append(entry)
    return results


# ─── Analysis 6: Bonferroni-Corrected p-values ──────────────────────────────


def compute_bonferroni_holm(analysis):
    """Apply Bonferroni and Holm step-down corrections to all 116 pairwise tests."""
    tests = analysis["pairwise_tests"]
    n_tests = len(tests)
    print(f"  Total pairwise tests: {n_tests}")

    # Sort by p-value for Holm
    indexed = [(i, t["p_value"]) for i, t in enumerate(tests)]
    indexed.sort(key=lambda x: x[1])

    bonferroni_alpha = 0.05 / n_tests

    results = []
    n_sig_uncorrected = 0
    n_sig_bonferroni = 0
    n_sig_holm = 0

    for rank, (orig_idx, p_val) in enumerate(indexed):
        t = tests[orig_idx]

        # Bonferroni
        bonf_p = min(p_val * n_tests, 1.0)
        bonf_sig = bonf_p < 0.05

        # Holm step-down: compare to alpha / (m - rank)
        holm_alpha = 0.05 / (n_tests - rank)
        holm_sig = p_val < holm_alpha

        uncorr_sig = t.get("significant", p_val < 0.05)

        if uncorr_sig:
            n_sig_uncorrected += 1
        if bonf_sig:
            n_sig_bonferroni += 1
        if holm_sig:
            n_sig_holm += 1

        results.append(
            {
                "base_model": t["base_model"],
                "quant_higher": t["quant_higher"],
                "quant_lower": t["quant_lower"],
                "metric": t["metric"],
                "source": t["source"],
                "mean_higher": t["mean_higher"],
                "mean_lower": t["mean_lower"],
                "difference": t["difference"],
                "percent_change": t["percent_change"],
                "t_statistic": t["t_statistic"],
                "p_value_uncorrected": t["p_value"],
                "p_value_bonferroni": round(bonf_p, 6),
                "p_value_holm_rank": rank + 1,
                "holm_alpha": round(holm_alpha, 6),
                "effect_size": t["effect_size"],
                "significant_uncorrected": uncorr_sig,
                "significant_bonferroni": bonf_sig,
                "significant_holm": holm_sig,
            }
        )

    return {
        "n_tests": n_tests,
        "bonferroni_alpha": round(bonferroni_alpha, 6),
        "n_significant_uncorrected": n_sig_uncorrected,
        "n_significant_bonferroni": n_sig_bonferroni,
        "n_significant_holm": n_sig_holm,
        "tests": sorted(results, key=lambda x: x["p_value_uncorrected"]),
    }


# ─── Analysis 7: TOST Equivalence Tests ─────────────────────────────────────


def tost_test(mean_a, mean_b, std_a, std_b, n_a, n_b, margin):
    """Two One-Sided Tests for equivalence within ±margin.

    Returns (tost_p, equivalent) where tost_p is max(p_upper, p_lower).
    """
    diff = mean_b - mean_a  # lower quant minus baseline
    se = (
        math.sqrt(std_a**2 / n_a + std_b**2 / n_b)
        if (n_a > 0 and n_b > 0)
        else float("inf")
    )
    if se == 0 or se == float("inf"):
        return (1.0, False)

    # Welch's df
    num = (std_a**2 / n_a + std_b**2 / n_b) ** 2
    denom = (std_a**2 / n_a) ** 2 / max(n_a - 1, 1) + (std_b**2 / n_b) ** 2 / max(
        n_b - 1, 1
    )
    df = num / denom if denom > 0 else n_a + n_b - 2

    # Test 1: H0: diff <= -margin (lower bound)
    t_lower = (diff + margin) / se
    p_lower = 1 - stats.t.cdf(t_lower, df)

    # Test 2: H0: diff >= +margin (upper bound)
    t_upper = (diff - margin) / se
    p_upper = stats.t.cdf(t_upper, df)

    tost_p = max(p_lower, p_upper)
    return (round(tost_p, 6), tost_p < 0.05)


def compute_tost_equivalence(samples, analysis):
    """TOST equivalence tests for variants classified as 'negligible' tier."""
    # Build per-variant benchmark accuracy arrays from raw samples
    bench_samples = [s for s in samples if s["task_name"] in BENCH_TASKS]
    variant_scores = defaultdict(list)
    for s in bench_samples:
        # Use rescored_accuracy if available, else exact_match
        metrics = s.get("metrics", {})
        em = metrics.get("exact_match", {})
        score = em.get("score", 0) if isinstance(em, dict) else (em or 0)
        variant_scores[s["model"]].append(float(score))

    # Also compute from generation quality for gen metrics
    gen_samples = [s for s in samples if s["task_name"] in GEN_TASKS]
    variant_gen = defaultdict(lambda: defaultdict(list))
    for s in gen_samples:
        for metric in KEY_METRICS:
            if metric in s.get("metrics", {}):
                v = s["metrics"][metric]
                score = v.get("score", v) if isinstance(v, dict) else v
                if score is not None:
                    variant_gen[s["model"]][metric].append(float(score))

    # Identify negligible-tier variants from decision matrix
    # Get unique (model, quant) that have negligible tier
    negligible_variants = set()
    for entry in analysis.get("decision_matrix", []):
        if entry.get("quality_tier") == "negligible":
            negligible_variants.add(entry["model_name"])

    # For each negligible variant, find its baseline
    baselines = {}
    for entry in analysis["benchmark_accuracy"]:
        baseline = entry.get("primary_baseline", "Q8_0")
        base_model = entry["base_model"]
        if entry["quant_level"] == baseline:
            baselines[base_model] = entry["model_name"]

    results = []
    margins_pp = [0.03, 0.05]  # 3pp and 5pp equivalence margins
    margins_gen = [0.03, 0.05]  # 3% and 5% equivalence margins

    for entry in analysis["benchmark_accuracy"]:
        model_name = entry["model_name"]
        base_model = entry["base_model"]
        quant = entry["quant_level"]
        baseline_name = baselines.get(base_model)

        if (
            model_name not in negligible_variants
            or not baseline_name
            or model_name == baseline_name
        ):
            continue

        # Benchmark TOST at both margins
        scores_variant = variant_scores.get(model_name, [])
        scores_baseline = variant_scores.get(baseline_name, [])

        bench_results_by_margin = {}
        if len(scores_variant) >= 30 and len(scores_baseline) >= 30:
            mean_b = np.mean(scores_baseline)
            mean_v = np.mean(scores_variant)
            std_b = np.std(scores_baseline, ddof=1)
            std_v = np.std(scores_variant, ddof=1)
            for margin_pp in margins_pp:
                tost_p, equiv = tost_test(
                    mean_b,
                    mean_v,
                    std_b,
                    std_v,
                    len(scores_baseline),
                    len(scores_variant),
                    margin_pp,
                )
                bench_results_by_margin[f"{int(margin_pp*100)}pp"] = {
                    "tested": True,
                    "margin_pp": margin_pp * 100,
                    "baseline_mean": round(float(mean_b), 4),
                    "variant_mean": round(float(mean_v), 4),
                    "delta_pp": round(float((mean_v - mean_b) * 100), 1),
                    "tost_p": tost_p,
                    "equivalent": equiv,
                    "n_baseline": len(scores_baseline),
                    "n_variant": len(scores_variant),
                }

        # Generation TOST at both margins
        baseline_gen_vals = []
        variant_gen_vals = []
        for metric in KEY_METRICS:
            bl = variant_gen.get(baseline_name, {}).get(metric, [])
            vr = variant_gen.get(model_name, {}).get(metric, [])
            baseline_gen_vals.extend(bl)
            variant_gen_vals.extend(vr)

        gen_results_by_margin = {}
        if len(baseline_gen_vals) >= 30 and len(variant_gen_vals) >= 30:
            mean_bg = np.mean(baseline_gen_vals)
            mean_vg = np.mean(variant_gen_vals)
            std_bg = np.std(baseline_gen_vals, ddof=1)
            std_vg = np.std(variant_gen_vals, ddof=1)
            for margin_gen in margins_gen:
                abs_margin = margin_gen * mean_bg if mean_bg > 0 else margin_gen
                tost_p, equiv = tost_test(
                    mean_bg,
                    mean_vg,
                    std_bg,
                    std_vg,
                    len(baseline_gen_vals),
                    len(variant_gen_vals),
                    abs_margin,
                )
                gen_results_by_margin[f"{int(margin_gen*100)}pct"] = {
                    "tested": True,
                    "margin_pct": margin_gen * 100,
                    "margin_absolute": round(float(abs_margin), 4),
                    "baseline_mean": round(float(mean_bg), 4),
                    "variant_mean": round(float(mean_vg), 4),
                    "delta_pct": (
                        round(float((mean_vg - mean_bg) / mean_bg * 100), 1)
                        if mean_bg > 0
                        else 0.0
                    ),
                    "tost_p": tost_p,
                    "equivalent": equiv,
                    "n_baseline": len(baseline_gen_vals),
                    "n_variant": len(variant_gen_vals),
                }

        # Backward-compatible: keep benchmark_tost / generation_tost as 3pp results
        bench_3pp = bench_results_by_margin.get("3pp", {"tested": False})
        gen_3pct = gen_results_by_margin.get("3pct", {"tested": False})

        results.append(
            {
                "base_model": base_model,
                "quant_level": quant,
                "model_name": model_name,
                "tier": "negligible",
                "benchmark_tost": bench_3pp,
                "generation_tost": gen_3pct,
                "benchmark_tost_5pp": bench_results_by_margin.get(
                    "5pp", {"tested": False}
                ),
                "generation_tost_5pct": gen_results_by_margin.get(
                    "5pct", {"tested": False}
                ),
            }
        )

    return results


# ─── Analysis 8: TR123 Cost Cross-Reference ─────────────────────────────────


def extract_tr123_cross_ref(analysis):
    """Extract TR123 cross-reference data from cost_table."""
    results = []
    for entry in analysis["cost_table"]:
        results.append(
            {
                "base_model": entry["base_model"],
                "quant_level": entry["quant_level"],
                "native_tok_per_s": entry["native_tok_per_s"],
                "cost_per_1m_tokens": entry["cost_per_1m_tokens"],
                "primary_baseline_cost": entry.get("primary_cost_per_1m"),
                "savings_vs_primary_pct": entry.get("savings_vs_primary_pct"),
                "speedup_vs_primary": entry.get("speedup_vs_primary"),
                "tr123_cost_per_1m": entry.get("tr123_cost_per_1m"),
                "tr123_tok_per_s": entry.get("tr123_tok_per_s"),
            }
        )
    return results


# ─── Analysis 9: Full TTFT Table (all 34 variants) ──────────────────────────


def compute_full_ttft(analysis):
    """Extract complete TTFT data for all 34 variants."""
    results = []
    for entry in analysis["performance"]:
        base, quant = parse_model(entry["model"])
        results.append(
            {
                "base_model": base,
                "quant_level": quant,
                "model": entry["model"],
                "n_samples": entry["n_samples"],
                "ttft_mean_ms": entry.get("ttft_ms_mean"),
                "ttft_median_ms": entry.get("ttft_ms_median"),
                "ttft_std_ms": entry.get("ttft_ms_std"),
                "ttft_min_ms": entry.get("ttft_ms_min"),
                "ttft_max_ms": entry.get("ttft_ms_max"),
                "native_tok_per_s": entry.get("native_tok_per_s_mean"),
                "native_cv_pct": entry.get("native_cv_pct"),
                "http_overhead_pct": entry.get("http_overhead_pct"),
            }
        )
    return results


# ─── Analysis 10: Explicit 29-Variant Enumeration ───────────────────────────


def compute_29_variant_enumeration(analysis):
    """Enumerate ALL quantized variants (excluding baselines) with tier classification."""
    # Identify baselines
    baselines = set()
    for entry in analysis["benchmark_accuracy"]:
        if entry["quant_level"] == entry.get("primary_baseline"):
            baselines.add(entry["model_name"])

    # Enumerate non-baseline variants
    variants = []
    for entry in analysis["benchmark_accuracy"]:
        if entry["model_name"] in baselines:
            continue

        # Find quality info from quality_curves
        gen_delta = None
        for qc in analysis["quality_curves"]:
            if (
                qc["base_model"] == entry["base_model"]
                and qc["quant_level"] == entry["quant_level"]
            ):
                gen_delta = qc.get("key_metric_avg_delta_primary_pct", 0.0)
                break

        # Find tier from decision_matrix (use any vram_tier, tier is same)
        tier = "unknown"
        for dm in analysis["decision_matrix"]:
            if dm["model_name"] == entry["model_name"]:
                tier = dm["quality_tier"]
                break

        variants.append(
            {
                "base_model": entry["base_model"],
                "quant_level": entry["quant_level"],
                "model_name": entry["model_name"],
                "rescored_accuracy": round(entry["rescored_accuracy"] * 100, 1),
                "bench_delta_pp": entry["accuracy_delta_primary_pp"],
                "gen_quality_delta_pct": (
                    round(gen_delta, 2) if gen_delta is not None else None
                ),
                "quality_tier": tier,
                "is_safe": tier in ("negligible", "acceptable"),
            }
        )

    # Sort by model order then quant order
    def sort_key(v):
        m_idx = (
            MODEL_ORDER.index(v["base_model"]) if v["base_model"] in MODEL_ORDER else 99
        )
        q_idx = (
            QUANT_ORDER.index(v["quant_level"])
            if v["quant_level"] in QUANT_ORDER
            else 99
        )
        return (m_idx, q_idx)

    variants.sort(key=sort_key)

    n_safe = sum(1 for v in variants if v["is_safe"])
    n_total = len(variants)

    return {
        "n_total": n_total,
        "n_safe": n_safe,
        "n_unsafe": n_total - n_safe,
        "variants": variants,
        "tier_counts": {
            "negligible": sum(1 for v in variants if v["quality_tier"] == "negligible"),
            "acceptable": sum(1 for v in variants if v["quality_tier"] == "acceptable"),
            "concerning": sum(1 for v in variants if v["quality_tier"] == "concerning"),
            "unacceptable": sum(
                1 for v in variants if v["quality_tier"] == "unacceptable"
            ),
        },
    }


# ─── Main ────────────────────────────────────────────────────────────────────


def main():
    print("TR125 v2 Enhancement Analysis")
    print("=" * 60)

    print("\nLoading data...")
    samples = load_samples()
    analysis = load_analysis()

    results = {}

    print("\n1. Wilson CIs for benchmark accuracy...")
    results["wilson_cis"] = compute_wilson_cis(analysis)
    print(f"   Computed CIs for {len(results['wilson_cis'])} variants")

    print("\n2. MMLU vs ARC differential...")
    results["mmlu_arc_differential"] = compute_mmlu_arc_differential(analysis)
    print(
        f"   Computed differentials for {len(results['mmlu_arc_differential'])} variants"
    )

    print("\n3. Per-task generation quality...")
    results["per_task_generation"] = compute_per_task_generation(samples)
    print(f"   Computed {len(results['per_task_generation'])} task×variant entries")

    print("\n4. All 7 metrics...")
    results["all_7_metrics"] = extract_all_7_metrics(analysis)
    print(f"   Extracted 7 metrics for {len(results['all_7_metrics'])} variants")

    print("\n5. Timing outlier detection...")
    results["timing_outliers"] = compute_timing_outliers(samples)
    print(f"   Analyzed outliers for {len(results['timing_outliers'])} variants")

    print("\n6. Bonferroni & Holm corrections...")
    results["bonferroni_holm"] = compute_bonferroni_holm(analysis)
    print(
        f"   {results['bonferroni_holm']['n_significant_uncorrected']} sig uncorrected -> "
        f"{results['bonferroni_holm']['n_significant_bonferroni']} Bonferroni -> "
        f"{results['bonferroni_holm']['n_significant_holm']} Holm"
    )

    print("\n7. TOST equivalence tests (+-3pp and +-5pp)...")
    results["tost_equivalence"] = compute_tost_equivalence(samples, analysis)
    n_bench_3 = sum(
        1 for t in results["tost_equivalence"] if t["benchmark_tost"].get("equivalent")
    )
    n_gen_3 = sum(
        1 for t in results["tost_equivalence"] if t["generation_tost"].get("equivalent")
    )
    n_bench_5 = sum(
        1
        for t in results["tost_equivalence"]
        if t.get("benchmark_tost_5pp", {}).get("equivalent")
    )
    n_gen_5 = sum(
        1
        for t in results["tost_equivalence"]
        if t.get("generation_tost_5pct", {}).get("equivalent")
    )
    print(f"   {len(results['tost_equivalence'])} negligible variants tested:")
    print(f"   +-3pp: {n_bench_3} bench-equiv, {n_gen_3} gen-equiv")
    print(f"   +-5pp: {n_bench_5} bench-equiv, {n_gen_5} gen-equiv")

    print("\n8. TR123 cost cross-reference...")
    results["tr123_cross_ref"] = extract_tr123_cross_ref(analysis)
    print(f"   {len(results['tr123_cross_ref'])} cost entries")

    print("\n9. Full TTFT table...")
    results["full_ttft"] = compute_full_ttft(analysis)
    print(f"   {len(results['full_ttft'])} variants with complete TTFT data")

    print("\n10. 29-variant enumeration...")
    results["variant_enumeration"] = compute_29_variant_enumeration(analysis)
    ve = results["variant_enumeration"]
    print(
        f"   {ve['n_total']} quantized variants: {ve['n_safe']} safe, {ve['n_unsafe']} unsafe"
    )
    print(f"   Tiers: {ve['tier_counts']}")

    # Write output
    print(f"\nWriting results to {OUTPUT_PATH}...")

    # Custom JSON serializer for numpy types
    class NumpyEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, (np.integer,)):
                return int(obj)
            if isinstance(obj, (np.floating,)):
                return float(obj)
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            if isinstance(obj, np.bool_):
                return bool(obj)
            return super().default(obj)

    with open(OUTPUT_PATH, "w") as f:
        json.dump(results, f, indent=2, cls=NumpyEncoder)
    print(f"Done! Output: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
