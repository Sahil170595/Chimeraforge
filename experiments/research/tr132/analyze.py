"""TR132 Phase 5: 10-section analysis → analysis.json.

Sections:
1. Data Quality & Summary
2. Throughput Scaling (4-way: vLLM, TGI, Ollama, PyTorch)
3. H1: Per-Token Kernel Count
4. H2: Per-Token Memory Bandwidth
5. H3: GPU Utilization
6. H4: Kernel Signatures
7. H5: Baseline Overhead (vLLM N=1 vs PyTorch N=1)
8. Bandwidth Amortization Quantification
9. Hypothesis Verdicts (Holm-integrated, power-aware)
10. Causal Chain Synthesis
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np

from research.tr132.shared.cross_reference import (
    extract_tr131_degradation,
    extract_tr131_metrics,
    load_tr131_data,
)
from research.tr132.shared.statistics import (
    descriptive,
    holm_stepdown,
    pairwise_compare,
    power_analysis,
)

log = logging.getLogger("tr132.analyze")


# ── Helpers ──────────────────────────────────────────────────────────


def _safe_div(a: float, b: float, default: float = 0.0) -> float:
    return a / b if b != 0 else default


def _extract_rep_metrics(phase_results: dict) -> dict:
    """Extract per-model, per-N-level rep lists from phase results.

    Returns: {model_name: {"n1": [rep_dict, ...], "n8": [...]}}
    """
    out = {}
    for model_name, model_data in phase_results.get("models", {}).items():
        out[model_name] = {}
        for level_name, level_data in model_data.get("n_levels", {}).items():
            out[model_name][level_name] = [
                r for r in level_data.get("reps", []) if r.get("status") == "ok"
            ]
    return out


def _get_values(reps: list[dict], key: str, allow_zero: bool = False) -> list[float]:
    """Extract numeric values from rep dicts.

    By default drops zeros (invalid for TPS, kernel count).
    Set allow_zero=True for metrics where 0 is a valid measurement
    (e.g. gpu_utilization_pct).
    """
    values = []
    for r in reps:
        v = r.get(key)
        if v is not None and isinstance(v, (int, float)) and (allow_zero or v > 0):
            values.append(float(v))
    return values


def _for_each_backend_model(
    vllm_metrics: dict,
    tgi_metrics: dict,
    fn,
    **kwargs,
) -> dict:
    """Apply fn(model_name, model_data, backend_name, **kwargs) for each
    backend × model combination. Returns {backend: {model: result}}.
    """
    out = {}
    for backend_name, metrics in [("vllm", vllm_metrics), ("tgi", tgi_metrics)]:
        backend_out = {}
        for model_name, model_data in metrics.items():
            backend_out[model_name] = fn(model_name, model_data, backend_name, **kwargs)
        out[backend_name] = backend_out
    return out


# ── Section 1: Data Quality & Summary ────────────────────────────────


def _section_data_quality(
    vllm_results: dict,
    tgi_results: dict,
    tr131_data: dict,
) -> dict:
    section = {"section": "1_data_quality", "backends": {}}

    for name, results in [("vllm", vllm_results), ("tgi", tgi_results)]:
        backend_summary = {"models": {}}
        total_reps = 0
        ok_reps = 0

        for model_name, model_data in results.get("models", {}).items():
            model_summary = {}
            for level_name, level_data in model_data.get("n_levels", {}).items():
                reps = level_data.get("reps", [])
                n_ok = sum(1 for r in reps if r.get("status") == "ok")
                total_reps += len(reps)
                ok_reps += n_ok
                sizes = [
                    r.get("rep_size_mb", 0) for r in reps if r.get("status") == "ok"
                ]
                model_summary[level_name] = {
                    "total_reps": len(reps),
                    "ok_reps": n_ok,
                    "mean_trace_mb": (sum(sizes) / len(sizes) if sizes else 0),
                }
            backend_summary["models"][model_name] = model_summary

        backend_summary["total_reps"] = total_reps
        backend_summary["ok_reps"] = ok_reps
        backend_summary["success_rate_pct"] = (
            ok_reps / total_reps * 100 if total_reps > 0 else 0
        )
        section["backends"][name] = backend_summary

    # TR131 cross-reference status
    section["tr131_status"] = tr131_data.get("status", "not_found")
    section["tr131_run_dir"] = tr131_data.get("run_dir")

    # Power analysis for N=3 (honest about our limitations)
    section["power_analysis"] = power_analysis(n=3, alpha=0.05)
    section["statistical_caveat"] = (
        "With N=3 reps per condition, minimum detectable Cohen's d ~ 4.3. "
        "Only very large effects (>4 pooled SDs) can be detected as "
        "statistically significant. Effect sizes and direction are the "
        "primary evidence; p-values are reported but underpowered."
    )

    return section


# ── Section 2: Throughput Scaling (4-way) ────────────────────────────


def _section_throughput_scaling(
    vllm_metrics: dict,
    tgi_metrics: dict,
    tr131_metrics: dict,
) -> dict:
    """4-way per-agent TPS at N=1 and N=8, degradation ratios.

    Includes Ollama and PyTorch from TR131 for direct comparison.
    """
    section = {"section": "2_throughput_scaling", "comparisons": {}}

    all_models = set(list(vllm_metrics.keys()) + list(tgi_metrics.keys()))

    for model_name in sorted(all_models):
        model_comp = {}

        # ── TR132 backends (vLLM, TGI) ──
        for backend_name, metrics in [("vllm", vllm_metrics), ("tgi", tgi_metrics)]:
            model_data = metrics.get(model_name, {})
            n1_reps = model_data.get("n1", [])
            n8_reps = model_data.get("n8", [])

            n1_tps = _get_values(n1_reps, "per_agent_tps")
            n8_tps = _get_values(n8_reps, "per_agent_tps")

            entry = {}
            if n1_tps:
                entry["n1_tps"] = descriptive(n1_tps).to_dict()
            if n8_tps:
                entry["n8_tps"] = descriptive(n8_tps).to_dict()
            if n1_tps and n8_tps:
                n1_mean = float(np.mean(n1_tps))
                n8_mean = float(np.mean(n8_tps))
                entry["degradation_pct"] = (
                    round((1 - n8_mean / n1_mean) * 100, 1) if n1_mean > 0 else None
                )
                entry["scaling_ratio"] = (
                    round(n8_mean / n1_mean, 3) if n1_mean > 0 else None
                )
                if len(n1_tps) >= 2 and len(n8_tps) >= 2:
                    entry["n1_vs_n8"] = pairwise_compare(
                        n1_tps,
                        n8_tps,
                        f"{backend_name}_n1",
                        f"{backend_name}_n8",
                    ).to_dict()

            # Batching verification summary for N=8
            n8_batching = [
                r.get("batching_check", {}).get("batching_confirmed") for r in n8_reps
            ]
            entry["n8_batching_confirmed"] = all(
                b for b in n8_batching if b is not None
            )

            model_comp[backend_name] = entry

        # ── TR131 backends (Ollama, PyTorch) ──
        for tr_backend in ["ollama", "pytorch"]:
            for n_val in [1, 8]:
                key = f"{tr_backend}_n{n_val}"
                by_model = tr131_metrics.get(key, {})
                reps = by_model.get(model_name, [])
                if not reps:
                    continue

                tps_vals = [r["mean_tps"] for r in reps if r.get("mean_tps", 0) > 0]
                if not tps_vals:
                    continue

                n_label = f"n{n_val}"
                if tr_backend not in model_comp:
                    model_comp[tr_backend] = {"source": "TR131"}
                model_comp[tr_backend][f"{n_label}_tps"] = descriptive(
                    tps_vals
                ).to_dict()

            # Compute TR131 degradation
            n1_key = f"{tr_backend}_n1"
            n8_key = f"{tr_backend}_n8"
            n1_reps = tr131_metrics.get(n1_key, {}).get(model_name, [])
            n8_reps = tr131_metrics.get(n8_key, {}).get(model_name, [])
            n1_tps = [r["mean_tps"] for r in n1_reps if r.get("mean_tps", 0) > 0]
            n8_tps = [r["mean_tps"] for r in n8_reps if r.get("mean_tps", 0) > 0]
            if n1_tps and n8_tps and tr_backend in model_comp:
                n1_mean = float(np.mean(n1_tps))
                n8_mean = float(np.mean(n8_tps))
                model_comp[tr_backend]["degradation_pct"] = (
                    round((1 - n8_mean / n1_mean) * 100, 1) if n1_mean > 0 else None
                )

        section["comparisons"][model_name] = model_comp

    return section


# ── Section 3: H1 — Per-Token Kernel Count ──────────────────────────


def _h1_for_model(model_name, model_data, backend_name):
    n1_reps = model_data.get("n1", [])
    n8_reps = model_data.get("n8", [])

    n1_kpt = [
        _safe_div(r.get("kernel_count", 0), r.get("total_tokens", 1))
        for r in n1_reps
        if r.get("total_tokens", 0) > 0
    ]
    n8_kpt = [
        _safe_div(r.get("kernel_count", 0), r.get("total_tokens", 1))
        for r in n8_reps
        if r.get("total_tokens", 0) > 0
    ]

    entry = {}
    if n1_kpt:
        entry["n1_kernels_per_token"] = descriptive(n1_kpt).to_dict()
    if n8_kpt:
        entry["n8_kernels_per_token"] = descriptive(n8_kpt).to_dict()
    if n1_kpt and n8_kpt:
        n1_mean = float(np.mean(n1_kpt))
        n8_mean = float(np.mean(n8_kpt))
        entry["reduction_pct"] = (
            round((1 - n8_mean / n1_mean) * 100, 1) if n1_mean > 0 else None
        )
        entry["direction_confirmed"] = n8_mean < n1_mean
        if len(n1_kpt) >= 2 and len(n8_kpt) >= 2:
            entry["comparison"] = pairwise_compare(n1_kpt, n8_kpt, "n1", "n8").to_dict()
    return entry


def _section_h1_kernel_count(vllm_metrics, tgi_metrics):
    return {
        "section": "3_h1_kernel_count",
        "results": _for_each_backend_model(vllm_metrics, tgi_metrics, _h1_for_model),
    }


# ── Section 4: H2 — Per-Token Memory Bandwidth ──────────────────────


def _h2_for_model(model_name, model_data, backend_name):
    n1_reps = model_data.get("n1", [])
    n8_reps = model_data.get("n8", [])

    n1_mpt = [
        _safe_div(r.get("mem_time_ms", 0), r.get("total_tokens", 1))
        for r in n1_reps
        if r.get("total_tokens", 0) > 0
    ]
    n8_mpt = [
        _safe_div(r.get("mem_time_ms", 0), r.get("total_tokens", 1))
        for r in n8_reps
        if r.get("total_tokens", 0) > 0
    ]

    entry = {}
    if n1_mpt:
        entry["n1_mem_time_per_token_ms"] = descriptive(n1_mpt).to_dict()
    if n8_mpt:
        entry["n8_mem_time_per_token_ms"] = descriptive(n8_mpt).to_dict()
    if n1_mpt and n8_mpt:
        n1_mean = float(np.mean(n1_mpt))
        n8_mean = float(np.mean(n8_mpt))
        entry["change_pct"] = (
            round((n8_mean / n1_mean - 1) * 100, 1) if n1_mean > 0 else None
        )
        entry["direction_confirmed"] = n8_mean < n1_mean
        if len(n1_mpt) >= 2 and len(n8_mpt) >= 2:
            entry["comparison"] = pairwise_compare(n1_mpt, n8_mpt, "n1", "n8").to_dict()
    return entry


def _section_h2_memory_bandwidth(vllm_metrics, tgi_metrics):
    return {
        "section": "4_h2_memory_bandwidth",
        "results": _for_each_backend_model(vllm_metrics, tgi_metrics, _h2_for_model),
    }


# ── Section 5: H3 — GPU Utilization ─────────────────────────────────


def _h3_for_model(model_name, model_data, backend_name):
    n1_reps = model_data.get("n1", [])
    n8_reps = model_data.get("n8", [])

    n1_util = _get_values(n1_reps, "gpu_utilization_pct", allow_zero=True)
    n8_util = _get_values(n8_reps, "gpu_utilization_pct", allow_zero=True)
    n8_concurrent = _get_values(n8_reps, "max_concurrent_kernels", allow_zero=True)

    entry = {}
    if n1_util:
        entry["n1_gpu_util_pct"] = descriptive(n1_util).to_dict()
    if n8_util:
        entry["n8_gpu_util_pct"] = descriptive(n8_util).to_dict()
    if n8_concurrent:
        entry["n8_max_concurrent_kernels"] = descriptive(n8_concurrent).to_dict()
    if n1_util and n8_util:
        entry["util_change_pct"] = round(
            float(np.mean(n8_util)) - float(np.mean(n1_util)), 1
        )
        entry["direction_confirmed"] = float(np.mean(n8_util)) > float(np.mean(n1_util))
        if len(n1_util) >= 2 and len(n8_util) >= 2:
            entry["comparison"] = pairwise_compare(
                n1_util, n8_util, "n1", "n8"
            ).to_dict()
    return entry


def _section_h3_gpu_utilization(vllm_metrics, tgi_metrics):
    return {
        "section": "5_h3_gpu_utilization",
        "results": _for_each_backend_model(vllm_metrics, tgi_metrics, _h3_for_model),
    }


# ── Section 6: H4 — Kernel Signatures ───────────────────────────────


def _h4_for_model(model_name, model_data, backend_name):
    n8_reps = model_data.get("n8", [])
    all_top_kernels = {}
    classifications = []

    for rep in n8_reps:
        for k in rep.get("top_kernels", []):
            name = k["name"]
            if name not in all_top_kernels:
                all_top_kernels[name] = {
                    "name": name,
                    "total_time_ms": 0,
                    "total_instances": 0,
                }
            all_top_kernels[name]["total_time_ms"] += k.get("time_ms", 0)
            all_top_kernels[name]["total_instances"] += k.get("instances", 0)

        kc = rep.get("kernel_classification", {})
        if kc:
            classifications.append(kc)

    sorted_kernels = sorted(
        all_top_kernels.values(), key=lambda x: x["total_time_ms"], reverse=True
    )

    # Identify attention type from kernel names
    attention_type = "unknown"
    for k in sorted_kernels:
        name_lower = k["name"].lower()
        if "paged" in name_lower or "page" in name_lower:
            attention_type = "paged_attention"
            break
        if "flash" in name_lower:
            attention_type = "flash_attention"
            break
        if "attention" in name_lower or "attn" in name_lower:
            attention_type = "standard_attention"
            break

    avg_class = {}
    if classifications:
        for key in ["gemm_pct", "attention_pct", "other_pct"]:
            vals = [c.get(key, 0) for c in classifications]
            avg_class[key] = round(float(np.mean(vals)), 1) if vals else 0

    return {
        "attention_type": attention_type,
        "top_kernels": sorted_kernels[:10],
        "avg_classification": avg_class,
    }


def _section_h4_kernel_signatures(vllm_metrics, tgi_metrics):
    return {
        "section": "6_h4_kernel_signatures",
        "results": _for_each_backend_model(vllm_metrics, tgi_metrics, _h4_for_model),
    }


# ── Section 7: H5 — Baseline Overhead (4-way N=1) ───────────────────


def _section_h5_baseline_overhead(
    vllm_metrics: dict,
    tgi_metrics: dict,
    tr131_metrics: dict,
) -> dict:
    """Compare N=1 baselines across all 4 backends.

    If vLLM N=1 ≈ PyTorch N=1 TPS, then batching (not serving overhead)
    explains the N=8 scaling advantage.
    """
    section = {"section": "7_h5_baseline_overhead", "comparisons": {}}

    all_models = set(list(vllm_metrics.keys()) + list(tgi_metrics.keys()))

    for model_name in sorted(all_models):
        model_comp = {}

        # TR132 backends at N=1
        for backend_name, metrics in [("vllm", vllm_metrics), ("tgi", tgi_metrics)]:
            model_data = metrics.get(model_name, {})
            n1_reps = model_data.get("n1", [])
            n1_tps = _get_values(n1_reps, "mean_tps")
            n1_gpu_ms = _get_values(n1_reps, "gpu_time_ms")
            n1_kernels = _get_values(n1_reps, "kernel_count")

            entry = {}
            if n1_tps:
                entry["n1_tps"] = descriptive(n1_tps).to_dict()
            if n1_gpu_ms:
                entry["n1_gpu_time_ms"] = descriptive(n1_gpu_ms).to_dict()
            if n1_kernels:
                entry["n1_kernel_count"] = descriptive(n1_kernels).to_dict()
            model_comp[backend_name] = entry

        # TR131 backends at N=1
        for tr_backend in ["ollama", "pytorch"]:
            n1_key = f"{tr_backend}_n1"
            by_model = tr131_metrics.get(n1_key, {})
            reps = by_model.get(model_name, [])
            if not reps:
                continue

            tps_vals = [r["mean_tps"] for r in reps if r.get("mean_tps", 0) > 0]
            gpu_time = [r["gpu_time_ms"] for r in reps if r.get("gpu_time_ms", 0) > 0]
            kernels = [r["kernel_count"] for r in reps if r.get("kernel_count", 0) > 0]

            entry = {"source": "TR131"}
            if tps_vals:
                entry["n1_tps"] = descriptive(tps_vals).to_dict()
            if gpu_time:
                entry["n1_gpu_time_ms"] = descriptive(gpu_time).to_dict()
            if kernels:
                entry["n1_kernel_count"] = descriptive(kernels).to_dict()
            model_comp[tr_backend] = entry

        # Cross-backend N=1 comparisons (the core of H5)
        pairwise_tests = []
        vllm_n1 = _get_values(
            vllm_metrics.get(model_name, {}).get("n1", []), "mean_tps"
        )
        pytorch_n1_reps = tr131_metrics.get("pytorch_n1", {}).get(model_name, [])
        pytorch_n1 = [
            r["mean_tps"] for r in pytorch_n1_reps if r.get("mean_tps", 0) > 0
        ]

        if len(vllm_n1) >= 2 and len(pytorch_n1) >= 2:
            pw = pairwise_compare(vllm_n1, pytorch_n1, "vllm_n1", "pytorch_n1")
            pairwise_tests.append(pw.to_dict())

            # H5 logic: if |delta_pct| < 20%, overhead is similar → batching
            # is the mechanism
            model_comp["h5_vllm_vs_pytorch"] = {
                "comparison": pw.to_dict(),
                "overhead_similar": abs(pw.delta_pct) < 20,
                "interpretation": (
                    "N=1 TPS within 20% — serving overhead comparable, "
                    "batching explains N=8 advantage"
                    if abs(pw.delta_pct) < 20
                    else f"N=1 TPS differ by {pw.delta_pct:.0f}% — serving "
                    f"overhead is also a factor"
                ),
            }
        elif vllm_n1 and pytorch_n1:
            # Not enough for t-test, use point estimates
            v_mean = float(np.mean(vllm_n1))
            p_mean = float(np.mean(pytorch_n1))
            pct_diff = abs(v_mean - p_mean) / p_mean * 100 if p_mean > 0 else 0
            model_comp["h5_vllm_vs_pytorch"] = {
                "vllm_n1_mean_tps": round(v_mean, 1),
                "pytorch_n1_mean_tps": round(p_mean, 1),
                "pct_diff": round(pct_diff, 1),
                "overhead_similar": pct_diff < 20,
                "note": "Insufficient reps for t-test; using point estimates",
            }

        section["comparisons"][model_name] = model_comp

    return section


# ── Section 8: Bandwidth Amortization ────────────────────────────────


def _section_bandwidth_amortization(
    vllm_metrics: dict,
    tgi_metrics: dict,
    tr131_degradation: dict,
) -> dict:
    """Quantify bandwidth amortization from continuous batching.

    Uses TR131 degradation data (loaded, not hardcoded) for comparison.
    """
    section = {"section": "8_bandwidth_amortization", "results": {}}

    for backend_name, metrics in [("vllm", vllm_metrics), ("tgi", tgi_metrics)]:
        backend_results = {}
        for model_name, model_data in metrics.items():
            n1_reps = model_data.get("n1", [])
            n8_reps = model_data.get("n8", [])

            n1_mpt = [
                _safe_div(r.get("mem_time_ms", 0), r.get("total_tokens", 1))
                for r in n1_reps
                if r.get("total_tokens", 0) > 0
            ]
            n8_mpt = [
                _safe_div(r.get("mem_time_ms", 0), r.get("total_tokens", 1))
                for r in n8_reps
                if r.get("total_tokens", 0) > 0
            ]

            n1_tps = _get_values(n1_reps, "per_agent_tps")
            n8_tps = _get_values(n8_reps, "per_agent_tps")

            entry = {}

            # Amortization ratio
            if n1_mpt and n8_mpt:
                n1_mean = float(np.mean(n1_mpt))
                n8_mean = float(np.mean(n8_mpt))
                amort_ratio = _safe_div(n1_mean, n8_mean)
                entry["amortization_ratio"] = round(amort_ratio, 2)
                entry["bandwidth_saving_pct"] = (
                    round((1 - 1 / amort_ratio) * 100, 1) if amort_ratio > 0 else 0
                )

            # Degradation comparison with TR131 data (loaded, not hardcoded)
            if n1_tps and n8_tps:
                n1_mean_tps = float(np.mean(n1_tps))
                n8_mean_tps = float(np.mean(n8_tps))
                degradation = _safe_div(n1_mean_tps - n8_mean_tps, n1_mean_tps) * 100
                entry["tps_degradation_pct"] = round(degradation, 1)

                # Compare with TR131 backends
                model_deg = tr131_degradation.get(model_name, {})
                for tr_backend in ["ollama", "pytorch"]:
                    tr_deg = model_deg.get(tr_backend, {})
                    tr_deg_pct = tr_deg.get("degradation_pct")
                    if tr_deg_pct is not None:
                        advantage = tr_deg_pct - degradation
                        entry[f"scaling_advantage_vs_{tr_backend}_pct"] = round(
                            advantage, 1
                        )
                        entry[f"{tr_backend}_degradation_pct"] = tr_deg_pct

                if not model_deg:
                    entry["tr131_comparison_note"] = (
                        "TR131 data not available for this model — "
                        "cannot compute scaling advantage"
                    )

            backend_results[model_name] = entry
        section["results"][backend_name] = backend_results

    return section


# ── Section 9: Hypothesis Verdicts ───────────────────────────────────


def _section_hypothesis_verdicts(
    h1_section: dict,
    h2_section: dict,
    h3_section: dict,
    h4_section: dict,
    h5_section: dict,
    alpha: float = 0.05,
) -> dict:
    """Verdicts require BOTH directional confirmation AND statistical
    significance (after Holm correction).  When significance cannot be
    achieved (N=3 power limitation), verdict is SUPPORTED (not CONFIRMED)
    based on consistent direction and large effect size.
    """
    section = {"section": "9_hypothesis_verdicts", "hypotheses": {}}

    p_values = []  # Collected for Holm correction

    # ── H1: Batching reduces per-token kernel count ──
    h1_tests = []
    for backend in ["vllm", "tgi"]:
        for model_name, data in h1_section.get("results", {}).get(backend, {}).items():
            comp = data.get("comparison", {})
            direction = data.get("direction_confirmed", False)
            p = comp.get("p_value", 1.0)
            d = abs(comp.get("cohens_d", 0))
            label = f"H1_{backend}_{model_name}"
            if comp:
                p_values.append((label, p))
            h1_tests.append(
                {
                    "label": label,
                    "direction_confirmed": direction,
                    "p_value": p if comp else None,
                    "cohens_d": d if comp else None,
                    "effect_size": comp.get("effect_size", ""),
                }
            )

    # ── H2: Batching reduces per-token memory bandwidth ──
    h2_tests = []
    for backend in ["vllm", "tgi"]:
        for model_name, data in h2_section.get("results", {}).get(backend, {}).items():
            comp = data.get("comparison", {})
            direction = data.get("direction_confirmed", False)
            p = comp.get("p_value", 1.0)
            d = abs(comp.get("cohens_d", 0))
            label = f"H2_{backend}_{model_name}"
            if comp:
                p_values.append((label, p))
            h2_tests.append(
                {
                    "label": label,
                    "direction_confirmed": direction,
                    "p_value": p if comp else None,
                    "cohens_d": d if comp else None,
                }
            )

    # ── H3: Batched serving achieves higher GPU utilization ──
    h3_tests = []
    for backend in ["vllm", "tgi"]:
        for model_name, data in h3_section.get("results", {}).get(backend, {}).items():
            comp = data.get("comparison", {})
            direction = data.get("direction_confirmed", False)
            p = comp.get("p_value", 1.0)
            d = abs(comp.get("cohens_d", 0))
            label = f"H3_{backend}_{model_name}"
            if comp:
                p_values.append((label, p))
            h3_tests.append(
                {
                    "label": label,
                    "direction_confirmed": direction,
                    "p_value": p if comp else None,
                    "cohens_d": d if comp else None,
                }
            )

    # Holm correction across ALL hypothesis tests
    holm_results = {}
    if p_values:
        holm_list = holm_stepdown(p_values, alpha=alpha)
        for item in holm_list:
            holm_results[item["label"]] = item

    # ── Verdict logic ──
    def _verdict_for_tests(tests: list[dict], hypothesis: str) -> dict:
        """Determine verdict from test results + Holm correction.

        CONFIRMED: direction + significant after Holm in ALL tests
        SUPPORTED: direction in all tests + large effect, but not significant
                   (expected with N=3)
        MIXED: direction in some tests
        REJECTED: direction wrong in all tests
        INSUFFICIENT_DATA: no tests available
        """
        if not tests:
            return {"verdict": "INSUFFICIENT_DATA", "tests": []}

        for t in tests:
            label = t["label"]
            holm = holm_results.get(label, {})
            t["holm_significant"] = holm.get("significant_holm", False)
            t["holm_threshold"] = holm.get("holm_threshold")

        directions = [
            t["direction_confirmed"]
            for t in tests
            if t["direction_confirmed"] is not None
        ]
        holm_sigs = [t["holm_significant"] for t in tests]
        large_effects = [
            t.get("cohens_d", 0) is not None and (t.get("cohens_d") or 0) >= 0.8
            for t in tests
        ]

        if all(directions) and all(holm_sigs) and directions:
            verdict = "CONFIRMED"
        elif all(directions) and all(large_effects) and directions:
            verdict = "SUPPORTED"
        elif all(directions) and directions:
            verdict = "SUPPORTED_DIRECTIONAL"
        elif any(directions):
            verdict = "MIXED"
        elif not directions:
            verdict = "INSUFFICIENT_DATA"
        else:
            verdict = "REJECTED"

        return {
            "verdict": verdict,
            "n_tests": len(tests),
            "direction_confirmed": sum(1 for d in directions if d),
            "holm_significant": sum(1 for s in holm_sigs if s),
            "tests": tests,
        }

    section["hypotheses"]["H1"] = {
        "hypothesis": "Batching reduces per-token kernel count",
        **_verdict_for_tests(h1_tests, "H1"),
    }
    section["hypotheses"]["H2"] = {
        "hypothesis": "Batching reduces per-token memory bandwidth",
        **_verdict_for_tests(h2_tests, "H2"),
    }
    section["hypotheses"]["H3"] = {
        "hypothesis": "Batched serving achieves higher GPU utilization",
        **_verdict_for_tests(h3_tests, "H3"),
    }

    # H4: Distinct kernel signatures (qualitative, no p-value)
    vllm_types = set()
    tgi_types = set()
    for model_name, data in h4_section.get("results", {}).get("vllm", {}).items():
        vllm_types.add(data.get("attention_type", "unknown"))
    for model_name, data in h4_section.get("results", {}).get("tgi", {}).items():
        tgi_types.add(data.get("attention_type", "unknown"))

    distinct = (
        vllm_types != tgi_types
        and "unknown" not in vllm_types
        and "unknown" not in tgi_types
    )
    section["hypotheses"]["H4"] = {
        "hypothesis": "PagedAttention vs Flash Attention have distinct signatures",
        "verdict": "CONFIRMED" if distinct else "INCONCLUSIVE",
        "vllm_attention_types": sorted(vllm_types),
        "tgi_attention_types": sorted(tgi_types),
        "note": (
            "Both backends produced identifiable attention kernel types"
            if distinct
            else "Could not reliably identify attention kernel types from names"
        ),
    }

    # H5: Baseline overhead (from section 7)
    h5_overheads = []
    for model_name, comp in h5_section.get("comparisons", {}).items():
        h5_data = comp.get("h5_vllm_vs_pytorch", {})
        if h5_data:
            h5_overheads.append(h5_data.get("overhead_similar", False))

    if h5_overheads:
        all_similar = all(h5_overheads)
        section["hypotheses"]["H5"] = {
            "hypothesis": "vLLM N=1 ~ PyTorch N=1 (batching is the mechanism)",
            "verdict": "CONFIRMED" if all_similar else "MIXED",
            "overhead_similar_count": sum(h5_overheads),
            "total_models": len(h5_overheads),
        }
    else:
        section["hypotheses"]["H5"] = {
            "hypothesis": "vLLM N=1 ~ PyTorch N=1 (batching is the mechanism)",
            "verdict": "INSUFFICIENT_DATA",
            "note": "TR131 PyTorch N=1 data not available for comparison",
        }

    section["holm_correction"] = (
        [holm_results[k] for k in sorted(holm_results.keys())] if holm_results else []
    )

    section["power_caveat"] = (
        "N=3 reps yields minimum detectable d~4.3. SUPPORTED verdicts "
        "indicate consistent direction + large effect size despite "
        "insufficient power for formal significance."
    )

    return section


# ── Section 10: Causal Chain Synthesis ───────────────────────────────


def _section_causal_chain(
    throughput_section: dict,
    amortization_section: dict,
    verdict_section: dict,
    tr131_degradation: dict,
) -> dict:
    section = {
        "section": "10_causal_chain",
        "chain": {
            "tr129": "Per-agent throughput drops 63% at N=8 (Amdahl s=0.39-0.54)",
            "tr130": "vLLM/TGI scale 3-4x better than Ollama at N=8",
            "tr131": "GPU memory bandwidth saturation is root cause",
            "tr132": "PENDING",
        },
    }

    # Add TR131 degradation data to the chain narrative
    if tr131_degradation:
        for model, backends in tr131_degradation.items():
            for backend, data in backends.items():
                deg = data.get("degradation_pct")
                if deg is not None:
                    section["chain"]["tr131"] = (
                        f"GPU memory bandwidth saturation is root cause "
                        f"({backend} degrades {deg:.1f}% at N=8)"
                    )
                    break
            break  # Use first available model

    # Summarize TR132 findings
    verdicts = verdict_section.get("hypotheses", {})
    confirmed = [h for h, v in verdicts.items() if v.get("verdict") == "CONFIRMED"]
    supported = [
        h
        for h, v in verdicts.items()
        if v.get("verdict") in ("SUPPORTED", "SUPPORTED_DIRECTIONAL")
    ]
    mixed = [h for h, v in verdicts.items() if v.get("verdict") == "MIXED"]
    rejected = [h for h, v in verdicts.items() if v.get("verdict") == "REJECTED"]

    section["chain"]["tr132"] = (
        f"Confirmed: {confirmed}, Supported: {supported}, "
        f"Mixed: {mixed}, Rejected: {rejected}"
    )

    # Key quantitative findings
    key_findings = []
    for backend in ["vllm", "tgi"]:
        for model_name, data in (
            amortization_section.get("results", {}).get(backend, {}).items()
        ):
            amort = data.get("amortization_ratio")
            saving = data.get("bandwidth_saving_pct")
            deg = data.get("tps_degradation_pct")
            adv_ollama = data.get("scaling_advantage_vs_ollama_pct")
            adv_pytorch = data.get("scaling_advantage_vs_pytorch_pct")
            if amort is not None:
                key_findings.append(
                    {
                        "backend": backend,
                        "model": model_name,
                        "amortization_ratio": amort,
                        "bandwidth_saving_pct": saving,
                        "tps_degradation_pct": deg,
                        "scaling_advantage_vs_ollama_pct": adv_ollama,
                        "scaling_advantage_vs_pytorch_pct": adv_pytorch,
                    }
                )
    section["key_findings"] = key_findings

    return section


# ── Main analysis runner ─────────────────────────────────────────────


def run_analysis(
    run_dir: Path,
    vllm_results: dict | None = None,
    tgi_results: dict | None = None,
    tr131_data: dict | None = None,
    alpha: float = 0.05,
) -> dict:
    """Run full 10-section analysis."""
    log.info("Running TR132 analysis...")

    # Load results from disk if not provided
    if vllm_results is None:
        vllm_path = run_dir / "p2_vllm_results.json"
        if vllm_path.exists():
            with open(vllm_path, encoding="utf-8") as f:
                vllm_results = json.load(f)
        else:
            vllm_results = {"models": {}}

    if tgi_results is None:
        tgi_path = run_dir / "p3_tgi_results.json"
        if tgi_path.exists():
            with open(tgi_path, encoding="utf-8") as f:
                tgi_results = json.load(f)
        else:
            tgi_results = {"models": {}}

    if tr131_data is None:
        tr131_data = load_tr131_data()

    # Extract structured metrics
    vllm_metrics = _extract_rep_metrics(vllm_results)
    tgi_metrics = _extract_rep_metrics(tgi_results)
    tr131_metrics = extract_tr131_metrics(tr131_data)
    tr131_degradation = extract_tr131_degradation(tr131_metrics)

    analysis = {"experiment": "tr132", "sections": {}}

    log.info("Section 1: Data Quality & Summary")
    s1 = _section_data_quality(vllm_results, tgi_results, tr131_data)
    analysis["sections"]["1_data_quality"] = s1

    log.info("Section 2: Throughput Scaling (4-way)")
    s2 = _section_throughput_scaling(vllm_metrics, tgi_metrics, tr131_metrics)
    analysis["sections"]["2_throughput_scaling"] = s2

    log.info("Section 3: H1 — Per-Token Kernel Count")
    s3 = _section_h1_kernel_count(vllm_metrics, tgi_metrics)
    analysis["sections"]["3_h1_kernel_count"] = s3

    log.info("Section 4: H2 — Per-Token Memory Bandwidth")
    s4 = _section_h2_memory_bandwidth(vllm_metrics, tgi_metrics)
    analysis["sections"]["4_h2_memory_bandwidth"] = s4

    log.info("Section 5: H3 — GPU Utilization")
    s5 = _section_h3_gpu_utilization(vllm_metrics, tgi_metrics)
    analysis["sections"]["5_h3_gpu_utilization"] = s5

    log.info("Section 6: H4 — Kernel Signatures")
    s6 = _section_h4_kernel_signatures(vllm_metrics, tgi_metrics)
    analysis["sections"]["6_h4_kernel_signatures"] = s6

    log.info("Section 7: H5 — Baseline Overhead (4-way N=1)")
    s7 = _section_h5_baseline_overhead(vllm_metrics, tgi_metrics, tr131_metrics)
    analysis["sections"]["7_h5_baseline_overhead"] = s7

    log.info("Section 8: Bandwidth Amortization")
    s8 = _section_bandwidth_amortization(vllm_metrics, tgi_metrics, tr131_degradation)
    analysis["sections"]["8_bandwidth_amortization"] = s8

    log.info("Section 9: Hypothesis Verdicts")
    s9 = _section_hypothesis_verdicts(s3, s4, s5, s6, s7, alpha=alpha)
    analysis["sections"]["9_hypothesis_verdicts"] = s9

    log.info("Section 10: Causal Chain Synthesis")
    s10 = _section_causal_chain(s2, s8, s9, tr131_degradation)
    analysis["sections"]["10_causal_chain"] = s10

    # Save
    analysis_dir = run_dir / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    analysis_path = analysis_dir / "analysis.json"
    with open(analysis_path, "w", encoding="utf-8") as f:
        json.dump(analysis, f, indent=2, default=str)
    log.info("Analysis saved: %s", analysis_path)

    return analysis
