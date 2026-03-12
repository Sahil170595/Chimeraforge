"""TR131 analysis — 12-section GPU profiling analysis with TR126-grade rigor.

Every comparison uses:
- Descriptive stats: mean, median, std, 95% CI, p90/p95/p99, IQR outlier detection
- Pairwise tests: Welch's t-test, Cohen's d, Mann-Whitney U
- Multiple comparison correction: Holm step-down
- Power analysis: minimum detectable effect at observed N
- Per-model breakdowns where applicable

Reads all phase results and produces analysis.json with:
 1. Summary
 2. Kernel profile comparison
 3. GPU utilization comparison
 4. Serialization analysis (H2 core test)
 5. GPU context switch analysis (H3)
 6. Memory bandwidth analysis (H1)
 7. WDDM queue analysis
 8. OS runtime analysis (H4)
 9. Memory allocation analysis (H5)
10. PyTorch vs Ollama comparison
11. Hypothesis verdicts (H1-H5)
12. TR130 cross-validation
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from research.tr131.shared.statistics import (
    descriptive,
    holm_stepdown,
    pairwise_compare,
    power_analysis,
)

log = logging.getLogger("tr131.analyze")


# ── Data Loaders ─────────────────────────────────────────────────────


def _load_phase_results(run_dir: Path, phase_prefix: str) -> list[dict]:
    """Load results JSON for a phase."""
    candidates = list(run_dir.glob(f"{phase_prefix}*_results.json"))
    if not candidates:
        return []
    with open(candidates[0], encoding="utf-8") as f:
        return json.load(f)


def _load_parsed_traces(exports_dir: Path, run_label: str) -> dict:
    """Load parsed trace data for a specific run."""
    path = exports_dir / f"{run_label}_parsed.json"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _group_by_model(runs: list[dict]) -> dict[str, list[dict]]:
    """Group phase runs by model name."""
    groups: dict[str, list[dict]] = {}
    for r in runs:
        model = r.get("model", "unknown")
        groups.setdefault(model, []).append(r)
    return groups


def _extract_metric(runs: list[dict], key: str) -> list[float]:
    """Extract a numeric metric from runs, filtering zeros/None."""
    vals = []
    for r in runs:
        v = r.get(key)
        if v is not None and v > 0:
            vals.append(float(v))
    return vals


def _extract_trace_metric(
    exports_dir: Path,
    runs: list[dict],
    report_key: str,
    metric_key: str,
) -> list[float]:
    """Extract a metric from parsed trace data across runs."""
    vals = []
    for r in runs:
        parsed = _load_parsed_traces(exports_dir, r["run_label"])
        report = parsed.get(report_key, {})
        v = report.get(metric_key)
        if v is not None and isinstance(v, (int, float)):
            vals.append(float(v))
    return vals


def _compare_phases(
    vals_a: list[float],
    vals_b: list[float],
    label_a: str,
    label_b: str,
) -> dict | None:
    """Run pairwise comparison if both groups have data. Returns dict or None."""
    if not vals_a or not vals_b:
        return None
    return pairwise_compare(vals_a, vals_b, label_a, label_b).to_dict()


def _per_model_compare(
    exports_dir: Path | None,
    n1_runs: list[dict],
    n8_runs: list[dict],
    prefix: str,
    metric_key: str = "mean_tps",
    from_traces: tuple[str, str] | None = None,
) -> dict:
    """Pairwise comparison per model.

    If from_traces=(report_key, metric_key), extract from parsed traces.
    Otherwise extract from run dict using metric_key.
    """
    models = sorted({r.get("model", "unknown") for r in n1_runs + n8_runs})
    results = {}
    for model in models:
        m_n1 = [r for r in n1_runs if r.get("model") == model]
        m_n8 = [r for r in n8_runs if r.get("model") == model]
        if from_traces and exports_dir:
            a = _extract_trace_metric(exports_dir, m_n1, from_traces[0], from_traces[1])
            b = _extract_trace_metric(exports_dir, m_n8, from_traces[0], from_traces[1])
        else:
            a = _extract_metric(m_n1, metric_key)
            b = _extract_metric(m_n8, metric_key)
        cmp = _compare_phases(a, b, f"{prefix}_n1_{model}", f"{prefix}_n8_{model}")
        if cmp:
            results[model] = cmp
    return results


# ── Section 1: Executive Summary ─────────────────────────────────────


def _section_1_summary(
    p2: list,
    p3: list,
    p4: list,
    p5: list,
    p6: list,
) -> dict:
    """Section 1: Executive summary with descriptive statistics and tests."""
    section: dict = {
        "title": "Executive Summary",
        "phases_completed": {
            "p2_ollama_n1": len(p2),
            "p3_ollama_n8": len(p3),
            "p4_pytorch_n1": len(p4),
            "p5_pytorch_n8": len(p5),
            "p6_ncu": len(p6),
        },
        "total_runs": len(p2) + len(p3) + len(p4) + len(p5) + len(p6),
    }

    # Aggregate TPS descriptive stats
    for label, runs in [
        ("ollama_n1", p2),
        ("ollama_n8", p3),
        ("pytorch_n1", p4),
        ("pytorch_n8", p5),
    ]:
        tps = _extract_metric(runs, "mean_tps")
        section[f"{label}_tps"] = descriptive(tps).to_dict() if tps else None

    # Per-model descriptive stats
    per_model: dict = {}
    for label, runs in [
        ("ollama_n1", p2),
        ("ollama_n8", p3),
        ("pytorch_n1", p4),
        ("pytorch_n8", p5),
    ]:
        for model, model_runs in _group_by_model(runs).items():
            per_model.setdefault(model, {})
            tps = _extract_metric(model_runs, "mean_tps")
            per_model[model][label] = descriptive(tps).to_dict() if tps else None
    section["per_model"] = per_model

    # Degradation tests (N=1 vs N=8)
    degradation = {}
    for prefix, n1, n8 in [("ollama", p2, p3), ("pytorch", p4, p5)]:
        cmp = _compare_phases(
            _extract_metric(n1, "mean_tps"),
            _extract_metric(n8, "mean_tps"),
            f"{prefix}_n1",
            f"{prefix}_n8",
        )
        if cmp:
            degradation[prefix] = cmp
    section["degradation_tests"] = degradation

    # Per-model degradation tests
    per_model_deg = {}
    for prefix, n1, n8 in [("ollama", p2, p3), ("pytorch", p4, p5)]:
        for model in sorted({r.get("model", "?") for r in n1 + n8}):
            m1 = _extract_metric([r for r in n1 if r.get("model") == model], "mean_tps")
            m8 = _extract_metric([r for r in n8 if r.get("model") == model], "mean_tps")
            cmp = _compare_phases(
                m1, m8, f"{prefix}_n1_{model}", f"{prefix}_n8_{model}"
            )
            if cmp:
                per_model_deg[f"{prefix}_{model}"] = cmp
    section["per_model_degradation"] = per_model_deg

    # Power analysis for each group
    section["power_analysis"] = {
        label: power_analysis(len(_extract_metric(runs, "mean_tps")))
        for label, runs in [
            ("ollama_n1", p2),
            ("ollama_n8", p3),
            ("pytorch_n1", p4),
            ("pytorch_n8", p5),
        ]
    }

    return section


# ── Section 2: Kernel Profile Comparison ─────────────────────────────


def _section_2_kernel_comparison(
    exports_dir: Path,
    p2: list,
    p3: list,
    p4: list,
    p5: list,
) -> dict:
    """Section 2: Kernel profile comparison with per-model breakdowns."""
    phases = {"ollama_n1": p2, "ollama_n8": p3, "pytorch_n1": p4, "pytorch_n8": p5}
    comparison: dict = {}

    for label, runs in phases.items():
        if not runs:
            continue

        # Per-run kernel stats
        instance_counts = []
        gpu_time_ms_vals = []
        gemm_pcts = []
        attn_pcts = []
        top_kernels_agg: dict[str, float] = {}

        for r in runs:
            parsed = _load_parsed_traces(exports_dir, r["run_label"])
            kern = parsed.get("cuda_gpu_kern_sum", {})
            inst = kern.get("total_instances", 0)
            gt = kern.get("total_gpu_time_ms", 0)
            if inst > 0:
                instance_counts.append(inst)
                gpu_time_ms_vals.append(gt)

            cls = kern.get("kernel_classification", {})
            g = cls.get("gemm_pct")
            a = cls.get("attention_pct")
            if g is not None:
                gemm_pcts.append(g)
            if a is not None:
                attn_pcts.append(a)

            for k in kern.get("top_10", []):
                name = k["name"][:80]
                top_kernels_agg[name] = (
                    top_kernels_agg.get(name, 0) + k["total_time_ms"]
                )

        sorted_kernels = sorted(
            top_kernels_agg.items(),
            key=lambda x: x[1],
            reverse=True,
        )

        comparison[label] = {
            "kernel_instances": (
                descriptive(instance_counts).to_dict() if instance_counts else None
            ),
            "gpu_time_ms": (
                descriptive(gpu_time_ms_vals).to_dict() if gpu_time_ms_vals else None
            ),
            "gemm_pct": descriptive(gemm_pcts).to_dict() if gemm_pcts else None,
            "attention_pct": descriptive(attn_pcts).to_dict() if attn_pcts else None,
            "top_5_kernels": [
                {"name": name, "total_time_ms": round(ms, 2)}
                for name, ms in sorted_kernels[:5]
            ],
        }

    # Per-model breakdowns
    per_model: dict = {}
    for label, runs in phases.items():
        for model, model_runs in _group_by_model(runs).items():
            per_model.setdefault(model, {})
            inst_vals = []
            gpu_vals = []
            for r in model_runs:
                parsed = _load_parsed_traces(exports_dir, r["run_label"])
                kern = parsed.get("cuda_gpu_kern_sum", {})
                i = kern.get("total_instances", 0)
                g = kern.get("total_gpu_time_ms", 0)
                if i > 0:
                    inst_vals.append(i)
                    gpu_vals.append(g)
            per_model[model][label] = {
                "kernel_instances": (
                    descriptive(inst_vals).to_dict() if inst_vals else None
                ),
                "gpu_time_ms": descriptive(gpu_vals).to_dict() if gpu_vals else None,
            }

    # Statistical tests: N=1 vs N=8 kernel counts
    tests = {}
    for prefix, n1, n8 in [("ollama", p2, p3), ("pytorch", p4, p5)]:
        a = _extract_trace_metric(
            exports_dir, n1, "cuda_gpu_kern_sum", "total_instances"
        )
        b = _extract_trace_metric(
            exports_dir, n8, "cuda_gpu_kern_sum", "total_instances"
        )
        cmp = _compare_phases(a, b, f"{prefix}_n1", f"{prefix}_n8")
        if cmp:
            tests[f"{prefix}_kernel_count_n1_vs_n8"] = cmp

    return {
        "title": "Kernel Profile Comparison",
        "comparison": comparison,
        "per_model": per_model,
        "statistical_tests": tests,
    }


# ── Section 3: GPU Utilization Comparison ────────────────────────────


def _section_3_gpu_utilization(
    exports_dir: Path,
    p2: list,
    p3: list,
    p4: list,
    p5: list,
) -> dict:
    """Section 3: GPU utilization with descriptive stats and pairwise tests."""
    phases = {"ollama_n1": p2, "ollama_n8": p3, "pytorch_n1": p4, "pytorch_n8": p5}
    comparison: dict = {}

    for label, runs in phases.items():
        if not runs:
            continue
        util = _extract_trace_metric(
            exports_dir, runs, "cuda_kern_exec_trace", "gpu_utilization_pct"
        )
        idle = _extract_trace_metric(
            exports_dir, runs, "cuda_kern_exec_trace", "gpu_idle_ms"
        )
        gap = _extract_trace_metric(
            exports_dir, runs, "cuda_kern_exec_trace", "mean_gap_us"
        )
        max_gap = _extract_trace_metric(
            exports_dir, runs, "cuda_kern_exec_trace", "max_gap_us"
        )

        comparison[label] = {
            "gpu_utilization_pct": descriptive(util).to_dict() if util else None,
            "gpu_idle_ms": descriptive(idle).to_dict() if idle else None,
            "mean_gap_us": descriptive(gap).to_dict() if gap else None,
            "max_gap_us": descriptive(max_gap).to_dict() if max_gap else None,
        }

    # Statistical tests
    tests = {}
    for prefix, n1, n8 in [("ollama", p2, p3), ("pytorch", p4, p5)]:
        for metric_key, metric_label in [
            ("gpu_utilization_pct", "utilization"),
            ("mean_gap_us", "inter_kernel_gap"),
        ]:
            a = _extract_trace_metric(
                exports_dir, n1, "cuda_kern_exec_trace", metric_key
            )
            b = _extract_trace_metric(
                exports_dir, n8, "cuda_kern_exec_trace", metric_key
            )
            cmp = _compare_phases(a, b, f"{prefix}_n1", f"{prefix}_n8")
            if cmp:
                tests[f"{prefix}_{metric_label}_n1_vs_n8"] = cmp

    # Per-model
    per_model: dict = {}
    for prefix, n1, n8 in [("ollama", p2, p3), ("pytorch", p4, p5)]:
        pm = _per_model_compare(
            exports_dir,
            n1,
            n8,
            prefix,
            from_traces=("cuda_kern_exec_trace", "gpu_utilization_pct"),
        )
        for model, cmp in pm.items():
            per_model.setdefault(model, {})[f"{prefix}_utilization"] = cmp

    return {
        "title": "GPU Utilization Comparison",
        "comparison": comparison,
        "statistical_tests": tests,
        "per_model": per_model,
    }


# ── Section 4: Serialization Analysis (H2 Core Test) ────────────────


def _section_4_serialization(
    exports_dir: Path,
    p2: list,
    p3: list,
    p4: list,
    p5: list,
) -> dict:
    """Section 4: Serialization — kernel overlap at N=1 vs N=8.

    This is the CORE test for H2: does Ollama serialize GPU work?
    """
    phases = {"ollama_n1": p2, "ollama_n8": p3, "pytorch_n1": p4, "pytorch_n8": p5}
    comparison: dict = {}

    for label, runs in phases.items():
        if not runs:
            continue
        max_concurrent = _extract_trace_metric(
            exports_dir, runs, "cuda_kern_exec_trace", "max_concurrent_kernels"
        )

        # Compute serialized percentage from concurrency distributions
        serialized_pcts = []
        for r in runs:
            parsed = _load_parsed_traces(exports_dir, r["run_label"])
            exec_data = parsed.get("cuda_kern_exec_trace", {})
            ct = exec_data.get("concurrency_time_ms", {})
            if ct:
                total = sum(float(v) for v in ct.values())
                serial = sum(float(ct.get(str(k), 0)) for k in [0, 1])
                serialized_pcts.append(serial / total * 100 if total > 0 else 100)

        comparison[label] = {
            "max_concurrent_kernels": (
                descriptive(max_concurrent).to_dict() if max_concurrent else None
            ),
            "serialized_pct": (
                descriptive(serialized_pcts).to_dict() if serialized_pcts else None
            ),
        }

    # Statistical tests: max concurrent kernels
    tests = {}
    for prefix, n1, n8 in [("ollama", p2, p3), ("pytorch", p4, p5)]:
        a = _extract_trace_metric(
            exports_dir, n1, "cuda_kern_exec_trace", "max_concurrent_kernels"
        )
        b = _extract_trace_metric(
            exports_dir, n8, "cuda_kern_exec_trace", "max_concurrent_kernels"
        )
        cmp = _compare_phases(a, b, f"{prefix}_n1", f"{prefix}_n8")
        if cmp:
            tests[f"{prefix}_max_concurrent_n1_vs_n8"] = cmp

    # Cross-platform: Ollama N=8 vs PyTorch N=8
    ollama_n8_mc = _extract_trace_metric(
        exports_dir, p3, "cuda_kern_exec_trace", "max_concurrent_kernels"
    )
    pytorch_n8_mc = _extract_trace_metric(
        exports_dir, p5, "cuda_kern_exec_trace", "max_concurrent_kernels"
    )
    cmp = _compare_phases(ollama_n8_mc, pytorch_n8_mc, "ollama_n8", "pytorch_n8")
    if cmp:
        tests["ollama_vs_pytorch_n8_concurrency"] = cmp

    # Per-model
    per_model = {}
    for prefix, n1, n8 in [("ollama", p2, p3), ("pytorch", p4, p5)]:
        pm = _per_model_compare(
            exports_dir,
            n1,
            n8,
            prefix,
            from_traces=("cuda_kern_exec_trace", "max_concurrent_kernels"),
        )
        for model, c in pm.items():
            per_model.setdefault(model, {})[f"{prefix}_concurrency"] = c

    # Verdict based on actual statistical evidence
    verdict = _serialization_verdict(comparison, tests)

    return {
        "title": "Serialization Analysis (H2 Core Test)",
        "comparison": comparison,
        "statistical_tests": tests,
        "per_model": per_model,
        "verdict": verdict,
    }


def _serialization_verdict(comparison: dict, tests: dict) -> dict:
    """Compute H2 verdict from statistical evidence."""
    v: dict = {"evidence_items": []}

    # Evidence 1: Ollama N=8 serialized percentage
    ollama_n8_ser = comparison.get("ollama_n8", {}).get("serialized_pct")
    if ollama_n8_ser and ollama_n8_ser.get("n", 0) > 0:
        mean_ser = ollama_n8_ser["mean"]
        ci = ollama_n8_ser.get("ci_95", [0, 0])
        v["ollama_n8_serialized_pct"] = {
            "mean": round(mean_ser, 1),
            "ci_95": [round(c, 1) for c in ci],
        }
        v["evidence_items"].append(
            {
                "test": "ollama_n8_serialized_pct",
                "value": round(mean_ser, 1),
                "threshold": 90,
                "supports_h2": mean_ser > 90,
            }
        )

    # Evidence 2: Ollama vs PyTorch N=8 concurrency
    cross = tests.get("ollama_vs_pytorch_n8_concurrency")
    if cross:
        v["evidence_items"].append(
            {
                "test": "ollama_vs_pytorch_n8_concurrency",
                "p_value": cross["p_value"],
                "cohens_d": cross["cohens_d"],
                "effect_size": cross["effect_size"],
                "significant": cross["significant_p05"],
                "supports_h2": cross["significant_p05"] and cross["delta_abs"] < 0,
            }
        )

    # Overall H2 score
    supporting = sum(1 for e in v["evidence_items"] if e.get("supports_h2"))
    total = len(v["evidence_items"])
    v["h2_support_ratio"] = f"{supporting}/{total}" if total > 0 else "0/0"
    v["h2_supported"] = supporting > total / 2 if total > 0 else False

    return v


# ── Section 5: GPU Context Switch Analysis (H3) ─────────────────────


def _section_5_context_switches(
    exports_dir: Path,
    p2: list,
    p3: list,
) -> dict:
    """Section 5: Context switch proxy — kernel gap analysis."""
    comparison: dict = {}
    for label, runs in [("ollama_n1", p2), ("ollama_n8", p3)]:
        if not runs:
            continue
        gaps = _extract_trace_metric(
            exports_dir, runs, "cuda_kern_exec_trace", "n_gaps"
        )
        mean_gap = _extract_trace_metric(
            exports_dir, runs, "cuda_kern_exec_trace", "mean_gap_us"
        )
        max_gap = _extract_trace_metric(
            exports_dir, runs, "cuda_kern_exec_trace", "max_gap_us"
        )
        comparison[label] = {
            "n_gaps": descriptive(gaps).to_dict() if gaps else None,
            "mean_gap_us": descriptive(mean_gap).to_dict() if mean_gap else None,
            "max_gap_us": descriptive(max_gap).to_dict() if max_gap else None,
        }

    # Statistical test: N=1 vs N=8 gap counts
    tests = {}
    for metric, mlabel in [("n_gaps", "gap_count"), ("mean_gap_us", "mean_gap")]:
        a = _extract_trace_metric(exports_dir, p2, "cuda_kern_exec_trace", metric)
        b = _extract_trace_metric(exports_dir, p3, "cuda_kern_exec_trace", metric)
        cmp = _compare_phases(a, b, "ollama_n1", "ollama_n8")
        if cmp:
            tests[f"{mlabel}_n1_vs_n8"] = cmp

    # Per-model
    per_model = _per_model_compare(
        exports_dir,
        p2,
        p3,
        "ollama",
        from_traces=("cuda_kern_exec_trace", "n_gaps"),
    )

    return {
        "title": "GPU Context Switch Analysis (H3)",
        "note": "gpuctxsw requires admin on Windows — using kernel gaps as proxy",
        "comparison": comparison,
        "statistical_tests": tests,
        "per_model": per_model,
    }


# ── Section 6: Memory Bandwidth Analysis (H1) ───────────────────────


def _section_6_memory_bandwidth(
    exports_dir: Path,
    p2: list,
    p3: list,
    p4: list,
    p5: list,
    ncu_results: list,
) -> dict:
    """Section 6: Memory bandwidth from nsys memory ops + ncu DRAM throughput."""
    phases = {"ollama_n1": p2, "ollama_n8": p3, "pytorch_n1": p4, "pytorch_n8": p5}
    comparison: dict = {}

    for label, runs in phases.items():
        if not runs:
            continue
        ops = _extract_trace_metric(
            exports_dir, runs, "cuda_gpu_mem_time_sum", "total_ops"
        )
        time_ms = _extract_trace_metric(
            exports_dir, runs, "cuda_gpu_mem_time_sum", "total_time_ms"
        )
        comparison[label] = {
            "total_ops": descriptive(ops).to_dict() if ops else None,
            "total_time_ms": descriptive(time_ms).to_dict() if time_ms else None,
        }

    # Statistical tests
    tests = {}
    for prefix, n1, n8 in [("ollama", p2, p3), ("pytorch", p4, p5)]:
        a = _extract_trace_metric(
            exports_dir, n1, "cuda_gpu_mem_time_sum", "total_time_ms"
        )
        b = _extract_trace_metric(
            exports_dir, n8, "cuda_gpu_mem_time_sum", "total_time_ms"
        )
        cmp = _compare_phases(a, b, f"{prefix}_n1", f"{prefix}_n8")
        if cmp:
            tests[f"{prefix}_mem_time_n1_vs_n8"] = cmp

    # ncu DRAM throughput per model
    ncu_summary: dict = {}
    for r in ncu_results:
        parsed = r.get("parsed", {})
        summary = parsed.get("summary", {})
        ncu_summary[r.get("model", "unknown")] = {
            "mean_dram_throughput_pct": summary.get("mean_dram_throughput_pct"),
            "mean_sm_occupancy_pct": summary.get("mean_sm_occupancy_pct"),
        }

    # H1 verdict
    saturated = any(
        (v.get("mean_dram_throughput_pct") or 0) > 80 for v in ncu_summary.values()
    )

    return {
        "title": "Memory Bandwidth Analysis (H1)",
        "nsys_comparison": comparison,
        "ncu_dram_throughput": ncu_summary,
        "statistical_tests": tests,
        "verdict": {
            "bandwidth_saturated": saturated,
            "confidence": "high" if ncu_summary else "low_no_ncu_data",
        },
    }


# ── Section 7: WDDM Queue Analysis ──────────────────────────────────


def _section_7_wddm_queue(
    exports_dir: Path,
    p2: list,
    p3: list,
) -> dict:
    """Section 7: WDDM queue — launch-to-execution latency proxy."""
    comparison: dict = {}
    for label, runs in [("ollama_n1", p2), ("ollama_n8", p3)]:
        if not runs:
            continue
        max_gaps = _extract_trace_metric(
            exports_dir, runs, "cuda_kern_exec_trace", "max_gap_us"
        )
        n_launches = _extract_trace_metric(
            exports_dir, runs, "cuda_kern_exec_trace", "n_launches"
        )
        comparison[label] = {
            "max_gap_us": descriptive(max_gaps).to_dict() if max_gaps else None,
            "n_launches": descriptive(n_launches).to_dict() if n_launches else None,
        }

    # Test max gap N=1 vs N=8
    tests = {}
    a = _extract_trace_metric(exports_dir, p2, "cuda_kern_exec_trace", "max_gap_us")
    b = _extract_trace_metric(exports_dir, p3, "cuda_kern_exec_trace", "max_gap_us")
    cmp = _compare_phases(a, b, "ollama_n1", "ollama_n8")
    if cmp:
        tests["max_gap_n1_vs_n8"] = cmp

    return {
        "title": "WDDM Queue Analysis",
        "note": "On Windows, WDDM schedules GPU work via kernel-mode queues. "
        "Large inter-kernel gaps at N=8 suggest WDDM queue contention.",
        "comparison": comparison,
        "statistical_tests": tests,
    }


# ── Section 8: OS Runtime Analysis (H4) ─────────────────────────────


def _section_8_os_runtime(
    exports_dir: Path,
    p2: list,
    p3: list,
) -> dict:
    """Section 8: OS runtime — thread scheduling and wait times."""
    comparison: dict = {}
    for label, runs in [("ollama_n1", p2), ("ollama_n8", p3)]:
        if not runs:
            continue
        wait_ms = _extract_trace_metric(exports_dir, runs, "osrt_sum", "total_time_ms")
        total_calls = _extract_trace_metric(
            exports_dir, runs, "osrt_sum", "total_calls"
        )

        # Aggregate top OS calls
        top_calls_agg: dict[str, float] = {}
        for r in runs:
            parsed = _load_parsed_traces(exports_dir, r["run_label"])
            osrt = parsed.get("osrt_sum", {})
            for call in osrt.get("top_10", []):
                name = call["name"]
                top_calls_agg[name] = top_calls_agg.get(name, 0) + call["time_ms"]

        sorted_calls = sorted(top_calls_agg.items(), key=lambda x: x[1], reverse=True)

        comparison[label] = {
            "total_wait_ms": descriptive(wait_ms).to_dict() if wait_ms else None,
            "total_calls": descriptive(total_calls).to_dict() if total_calls else None,
            "top_5_os_calls": [
                {"name": name, "total_ms": round(ms, 1)}
                for name, ms in sorted_calls[:5]
            ],
        }

    # Statistical test
    tests = {}
    a = _extract_trace_metric(exports_dir, p2, "osrt_sum", "total_time_ms")
    b = _extract_trace_metric(exports_dir, p3, "osrt_sum", "total_time_ms")
    cmp = _compare_phases(a, b, "ollama_n1", "ollama_n8")
    if cmp:
        tests["os_wait_n1_vs_n8"] = cmp

    # Per-model
    per_model = _per_model_compare(
        exports_dir,
        p2,
        p3,
        "ollama",
        from_traces=("osrt_sum", "total_time_ms"),
    )

    return {
        "title": "OS Runtime Analysis (H4)",
        "comparison": comparison,
        "statistical_tests": tests,
        "per_model": per_model,
    }


# ── Section 9: Memory Allocation Analysis (H5) ──────────────────────


def _section_9_memory_allocation(
    exports_dir: Path,
    p2: list,
    p3: list,
    p4: list,
    p5: list,
) -> dict:
    """Section 9: Memory allocation — cudaMalloc/cudaFree calls as KV-cache proxy."""
    phases = {"ollama_n1": p2, "ollama_n8": p3, "pytorch_n1": p4, "pytorch_n8": p5}
    comparison: dict = {}

    for label, runs in phases.items():
        if not runs:
            continue
        alloc_counts = []
        alloc_times = []

        for r in runs:
            parsed = _load_parsed_traces(exports_dir, r["run_label"])
            api = parsed.get("cuda_api_sum", {})
            run_alloc = 0
            run_time = 0.0
            for call in api.get("all", []):
                name = call.get("name", "")
                if "Malloc" in name or "Free" in name or "Alloc" in name:
                    run_alloc += call.get("num_calls", 0)
                    run_time += call.get("time_ms", 0)
            alloc_counts.append(run_alloc)
            alloc_times.append(run_time)

        comparison[label] = {
            "alloc_calls": (
                descriptive(alloc_counts).to_dict() if alloc_counts else None
            ),
            "alloc_time_ms": (
                descriptive(alloc_times).to_dict() if alloc_times else None
            ),
        }

    # Statistical tests
    tests = {}
    for prefix, n1, n8 in [("ollama", p2, p3), ("pytorch", p4, p5)]:
        # Extract alloc counts per run
        a_counts, b_counts = [], []
        for r in n1:
            parsed = _load_parsed_traces(exports_dir, r["run_label"])
            api = parsed.get("cuda_api_sum", {})
            c = sum(
                call.get("num_calls", 0)
                for call in api.get("all", [])
                if any(k in call.get("name", "") for k in ["Malloc", "Free", "Alloc"])
            )
            a_counts.append(c)
        for r in n8:
            parsed = _load_parsed_traces(exports_dir, r["run_label"])
            api = parsed.get("cuda_api_sum", {})
            c = sum(
                call.get("num_calls", 0)
                for call in api.get("all", [])
                if any(k in call.get("name", "") for k in ["Malloc", "Free", "Alloc"])
            )
            b_counts.append(c)
        cmp = _compare_phases(a_counts, b_counts, f"{prefix}_n1", f"{prefix}_n8")
        if cmp:
            tests[f"{prefix}_alloc_count_n1_vs_n8"] = cmp

    return {
        "title": "Memory Allocation Analysis (H5)",
        "comparison": comparison,
        "statistical_tests": tests,
    }


# ── Section 10: PyTorch vs Ollama Comparison ─────────────────────────


def _section_10_pytorch_vs_ollama(
    p2: list,
    p3: list,
    p4: list,
    p5: list,
) -> dict:
    """Section 10: PyTorch vs Ollama — isolates serving overhead."""
    tests: dict = {}

    # N=1: Ollama vs PyTorch
    cmp_n1 = _compare_phases(
        _extract_metric(p2, "mean_tps"),
        _extract_metric(p4, "mean_tps"),
        "ollama_n1",
        "pytorch_n1",
    )
    if cmp_n1:
        tests["n1_ollama_vs_pytorch"] = cmp_n1

    # N=8: Ollama vs PyTorch
    cmp_n8 = _compare_phases(
        _extract_metric(p3, "mean_tps"),
        _extract_metric(p5, "mean_tps"),
        "ollama_n8",
        "pytorch_n8",
    )
    if cmp_n8:
        tests["n8_ollama_vs_pytorch"] = cmp_n8

    # Per-model N=1 and N=8 comparisons
    per_model: dict = {}
    for n_label, ollama_runs, pytorch_runs in [
        ("n1", p2, p4),
        ("n8", p3, p5),
    ]:
        models = sorted({r.get("model", "?") for r in ollama_runs + pytorch_runs})
        for model in models:
            o_tps = _extract_metric(
                [r for r in ollama_runs if r.get("model") == model], "mean_tps"
            )
            p_tps = _extract_metric(
                [r for r in pytorch_runs if r.get("model") == model], "mean_tps"
            )
            cmp = _compare_phases(
                o_tps, p_tps, f"ollama_{n_label}", f"pytorch_{n_label}"
            )
            if cmp:
                per_model.setdefault(model, {})[f"{n_label}_ollama_vs_pytorch"] = cmp

    # Degradation comparison: Ollama N=1→N=8 vs PyTorch N=1→N=8
    degradation: dict = {}
    for prefix, n1, n8 in [("ollama", p2, p3), ("pytorch", p4, p5)]:
        n1_tps = _extract_metric(n1, "mean_tps")
        n8_tps = _extract_metric(n8, "mean_tps")
        n1_desc = descriptive(n1_tps)
        n8_desc = descriptive(n8_tps)
        if n1_desc.mean > 0:
            deg_pct = (1 - n8_desc.mean / n1_desc.mean) * 100
            degradation[prefix] = {
                "n1_tps": n1_desc.to_dict(),
                "n8_tps": n8_desc.to_dict(),
                "degradation_pct": round(deg_pct, 1),
                "degradation_ci_note": "See degradation_tests in section 1 for full CI",
            }

    # Attribution
    ollama_deg = degradation.get("ollama", {}).get("degradation_pct", 0)
    pytorch_deg = degradation.get("pytorch", {}).get("degradation_pct", 0)
    attribution = {
        "ollama_total_degradation_pct": ollama_deg,
        "pytorch_total_degradation_pct": pytorch_deg,
        "attributable_to_ollama_pct": round(ollama_deg - pytorch_deg, 1),
        "attributable_to_gpu_physics_pct": round(pytorch_deg, 1),
    }

    return {
        "title": "PyTorch vs Ollama Comparison",
        "statistical_tests": tests,
        "per_model": per_model,
        "degradation_comparison": degradation,
        "attribution": attribution,
    }


# ── Section 11: Hypothesis Verdicts ──────────────────────────────────


def _section_11_hypothesis_verdicts(
    sections: dict[str, dict],
) -> dict:
    """Section 11: Evidence-weighted hypothesis verdicts.

    Each hypothesis is scored from actual p-values, effect sizes, and CIs.
    No hardcoded verdicts — everything flows from statistical evidence.
    """
    verdicts: dict = {}
    all_p_values: list[tuple[str, float]] = []

    # ── H1: GPU memory bandwidth saturation ──
    s6 = sections["s6"]
    h1_evidence = []
    bw_saturated = s6.get("verdict", {}).get("bandwidth_saturated", False)
    h1_evidence.append(
        {
            "source": "ncu_dram_throughput",
            "supports_h1": bw_saturated,
            "detail": s6.get("ncu_dram_throughput", {}),
        }
    )
    # If memory time N=1→N=8 changes significantly, bandwidth may be stressed
    mem_test = s6.get("statistical_tests", {}).get("ollama_mem_time_n1_vs_n8")
    if mem_test:
        h1_evidence.append(
            {
                "source": "nsys_mem_time_change",
                "p_value": mem_test["p_value"],
                "cohens_d": mem_test["cohens_d"],
                "significant": mem_test["significant_p05"],
                "supports_h1": mem_test["significant_p05"]
                and mem_test["delta_abs"] > 0,
            }
        )
        all_p_values.append(("H1_mem_time", mem_test["p_value"]))

    h1_support = sum(1 for e in h1_evidence if e.get("supports_h1"))
    verdicts["H1_bandwidth_saturation"] = {
        "hypothesis": "GPU memory bandwidth is saturated at N=1, limiting N=8 throughput",
        "evidence": h1_evidence,
        "support_ratio": f"{h1_support}/{len(h1_evidence)}",
        "verdict": _verdict_from_evidence(h1_support, len(h1_evidence)),
        "confidence": "high" if s6.get("ncu_dram_throughput") else "low",
    }

    # ── H2: Ollama request serialization ──
    s4 = sections["s4"]
    h2_evidence = []

    # Serialized percentage
    ser_data = s4.get("verdict", {}).get("ollama_n8_serialized_pct")
    if ser_data:
        h2_evidence.append(
            {
                "source": "ollama_n8_serialized_pct",
                "mean": ser_data["mean"],
                "ci_95": ser_data.get("ci_95"),
                "supports_h2": ser_data["mean"] > 90,
            }
        )

    # Concurrency test
    conc_test = s4.get("statistical_tests", {}).get("ollama_vs_pytorch_n8_concurrency")
    if conc_test:
        h2_evidence.append(
            {
                "source": "ollama_vs_pytorch_n8_concurrency",
                "p_value": conc_test["p_value"],
                "cohens_d": conc_test["cohens_d"],
                "effect_size": conc_test["effect_size"],
                "significant": conc_test["significant_p05"],
                "supports_h2": conc_test["significant_p05"],
            }
        )
        all_p_values.append(("H2_concurrency", conc_test["p_value"]))

    # Ollama N=1 vs N=8 max concurrent
    ollama_mc = s4.get("statistical_tests", {}).get("ollama_max_concurrent_n1_vs_n8")
    if ollama_mc:
        h2_evidence.append(
            {
                "source": "ollama_max_concurrent_n1_vs_n8",
                "p_value": ollama_mc["p_value"],
                "cohens_d": ollama_mc["cohens_d"],
                "supports_h2": not ollama_mc[
                    "significant_p05"
                ],  # No change = serialized
            }
        )
        all_p_values.append(("H2_ollama_mc", ollama_mc["p_value"]))

    h2_support = sum(1 for e in h2_evidence if e.get("supports_h2"))
    verdicts["H2_ollama_serialization"] = {
        "hypothesis": "Ollama serializes GPU requests even under concurrency",
        "evidence": h2_evidence,
        "support_ratio": f"{h2_support}/{len(h2_evidence)}",
        "verdict": _verdict_from_evidence(h2_support, len(h2_evidence)),
        "confidence": "high" if len(h2_evidence) >= 2 else "low",
    }

    # ── H3: CUDA context switching ──
    s5 = sections["s5"]
    h3_evidence = []
    gap_test = s5.get("statistical_tests", {}).get("gap_count_n1_vs_n8")
    if gap_test:
        h3_evidence.append(
            {
                "source": "gap_count_n1_vs_n8",
                "p_value": gap_test["p_value"],
                "cohens_d": gap_test["cohens_d"],
                "effect_size": gap_test["effect_size"],
                "significant": gap_test["significant_p05"],
                "supports_h3": gap_test["significant_p05"]
                and gap_test["delta_abs"] > 0,
            }
        )
        all_p_values.append(("H3_gap_count", gap_test["p_value"]))

    mean_gap_test = s5.get("statistical_tests", {}).get("mean_gap_n1_vs_n8")
    if mean_gap_test:
        h3_evidence.append(
            {
                "source": "mean_gap_n1_vs_n8",
                "p_value": mean_gap_test["p_value"],
                "cohens_d": mean_gap_test["cohens_d"],
                "significant": mean_gap_test["significant_p05"],
                "supports_h3": mean_gap_test["significant_p05"]
                and mean_gap_test["delta_abs"] > 0,
            }
        )
        all_p_values.append(("H3_mean_gap", mean_gap_test["p_value"]))

    h3_support = sum(1 for e in h3_evidence if e.get("supports_h3"))
    verdicts["H3_context_switching"] = {
        "hypothesis": "CUDA context switches increase significantly at N=8",
        "evidence": h3_evidence,
        "support_ratio": f"{h3_support}/{len(h3_evidence)}",
        "verdict": _verdict_from_evidence(h3_support, len(h3_evidence)),
        "confidence": "medium" if h3_evidence else "low",
        "note": "gpuctxsw requires admin — using kernel gap count as proxy",
    }

    # ── H4: CPU scheduling bottleneck ──
    s8 = sections["s8"]
    h4_evidence = []
    os_test = s8.get("statistical_tests", {}).get("os_wait_n1_vs_n8")
    if os_test:
        h4_evidence.append(
            {
                "source": "os_wait_time_n1_vs_n8",
                "p_value": os_test["p_value"],
                "cohens_d": os_test["cohens_d"],
                "effect_size": os_test["effect_size"],
                "significant": os_test["significant_p05"],
                "supports_h4": os_test["significant_p05"] and os_test["delta_abs"] > 0,
            }
        )
        all_p_values.append(("H4_os_wait", os_test["p_value"]))

    h4_support = sum(1 for e in h4_evidence if e.get("supports_h4"))
    verdicts["H4_cpu_scheduling"] = {
        "hypothesis": "CPU thread scheduling becomes a bottleneck at N=8",
        "evidence": h4_evidence,
        "support_ratio": f"{h4_support}/{len(h4_evidence)}",
        "verdict": _verdict_from_evidence(h4_support, len(h4_evidence)),
        "confidence": "medium" if h4_evidence else "low",
    }

    # ── H5: KV-cache memory pressure ──
    s9 = sections["s9"]
    h5_evidence = []
    alloc_test = s9.get("statistical_tests", {}).get("ollama_alloc_count_n1_vs_n8")
    if alloc_test:
        h5_evidence.append(
            {
                "source": "alloc_count_n1_vs_n8",
                "p_value": alloc_test["p_value"],
                "cohens_d": alloc_test["cohens_d"],
                "effect_size": alloc_test["effect_size"],
                "significant": alloc_test["significant_p05"],
                "supports_h5": alloc_test["significant_p05"]
                and alloc_test["delta_abs"] > 0,
            }
        )
        all_p_values.append(("H5_alloc", alloc_test["p_value"]))

    h5_support = sum(1 for e in h5_evidence if e.get("supports_h5"))
    verdicts["H5_kv_cache_pressure"] = {
        "hypothesis": "KV-cache memory pressure reduces SM occupancy at N=8",
        "evidence": h5_evidence,
        "support_ratio": f"{h5_support}/{len(h5_evidence)}",
        "verdict": _verdict_from_evidence(h5_support, len(h5_evidence)),
        "confidence": "low",
    }

    # ── Multiple comparison correction ──
    holm_results = []
    if all_p_values:
        holm_results = holm_stepdown(all_p_values)

    # ── Primary cause determination ──
    # Rank hypotheses by support ratio, breaking ties by effect size
    ranked = []
    for hid, v in verdicts.items():
        parts = v["support_ratio"].split("/")
        support = int(parts[0])
        total = int(parts[1]) if int(parts[1]) > 0 else 1
        ratio = support / total
        # Get max effect size from evidence
        max_d = 0.0
        for e in v.get("evidence", []):
            d = abs(e.get("cohens_d", 0))
            if d > max_d:
                max_d = d
        ranked.append((hid, ratio, max_d, v["verdict"]))

    ranked.sort(key=lambda x: (x[1], x[2]), reverse=True)

    primary_cause = ranked[0][0] if ranked and ranked[0][1] > 0.5 else "INCONCLUSIVE"

    # Attribution from section 10
    s10 = sections["s10"]
    attribution = s10.get("attribution", {})

    return {
        "title": "Hypothesis Verdicts",
        "verdicts": verdicts,
        "holm_correction": holm_results,
        "hypothesis_ranking": [
            {
                "hypothesis": h,
                "support_ratio": round(r, 2),
                "max_effect_size": round(d, 3),
                "verdict": v,
            }
            for h, r, d, v in ranked
        ],
        "primary_cause": primary_cause,
        "degradation_attribution": attribution,
    }


def _verdict_from_evidence(supporting: int, total: int) -> str:
    """Map evidence ratio to verdict string."""
    if total == 0:
        return "INSUFFICIENT_DATA"
    ratio = supporting / total
    if ratio >= 0.75:
        return "CONFIRMED"
    if ratio >= 0.5:
        return "PARTIALLY_CONFIRMED"
    if ratio > 0:
        return "WEAK_EVIDENCE"
    return "REJECTED"


# ── Section 12: TR130 Cross-Validation ───────────────────────────────


def _section_12_tr130_crossval(
    p2: list,
    p3: list,
) -> dict:
    """Section 12: Cross-validation with TR130 unprofiled data."""
    section: dict = {
        "title": "TR130 Cross-Validation",
    }

    # Profiled data from this experiment
    profiled: dict = {}
    for label, runs in [("ollama_n1", p2), ("ollama_n8", p3)]:
        tps = _extract_metric(runs, "mean_tps")
        profiled[label] = descriptive(tps).to_dict() if tps else None

    section["profiled_tps"] = profiled

    # Try to load TR130 results for comparison
    tr130_data = _load_tr130_data()
    if tr130_data:
        section["tr130_unprofiled_tps"] = tr130_data
        # Compute overhead estimates
        for label in ["ollama_n1", "ollama_n8"]:
            profiled_mean = profiled.get(label, {}).get("mean", 0)
            unprofiled_mean = tr130_data.get(label, {}).get("mean", 0)
            if profiled_mean > 0 and unprofiled_mean > 0:
                overhead_pct = (1 - profiled_mean / unprofiled_mean) * 100
                section.setdefault("profiling_overhead_pct", {})[label] = round(
                    overhead_pct, 1
                )

        section["overhead_acceptable"] = all(
            abs(v) < 10 for v in section.get("profiling_overhead_pct", {}).values()
        )
    else:
        section["tr130_data_available"] = False
        section["note"] = (
            "TR130 results not found — cannot compute profiling overhead. "
            "Compare manually with TR130 report values."
        )

    return section


def _load_tr130_data() -> dict | None:
    """Try to load TR130 Ollama results for cross-validation."""
    tr130_dir = Path(__file__).resolve().parent.parent / "tr130" / "results"
    if not tr130_dir.exists():
        return None

    # Find latest run
    candidates = sorted(
        [p for p in tr130_dir.iterdir() if p.is_dir()],
        key=lambda p: p.name,
        reverse=True,
    )
    if not candidates:
        return None

    # Look for Ollama results
    run_dir = candidates[0]
    result = {}
    for label, prefix in [("ollama_n1", "n1"), ("ollama_n8", "n8")]:
        json_files = list(run_dir.glob(f"*ollama*{prefix}*.json"))
        if not json_files:
            json_files = list(run_dir.glob(f"*{prefix}*.json"))
        for jf in json_files:
            try:
                with open(jf, encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    tps_vals = [
                        r.get("mean_tps", r.get("tps", 0))
                        for r in data
                        if r.get("mean_tps", r.get("tps", 0)) > 0
                    ]
                    if tps_vals:
                        result[label] = descriptive(tps_vals).to_dict()
                        break
            except Exception:
                continue

    return result if result else None


# ── Main Analysis Entry Point ─────────────────────────────────────────


def run_analysis(run_dir: Path) -> dict:
    """Run full 12-section analysis on collected data.

    Args:
        run_dir: Path to run directory (contains phase results + exports/)

    Returns:
        Full analysis dict (also saved as analysis.json).
    """
    log.info("Running 12-section analysis on %s", run_dir)
    exports_dir = run_dir / "exports"

    # Load phase results
    p2 = _load_phase_results(run_dir, "p2_ollama_n1")
    p3 = _load_phase_results(run_dir, "p3_ollama_n8")
    p4 = _load_phase_results(run_dir, "p4_pytorch_n1")
    p5 = _load_phase_results(run_dir, "p5_pytorch_n8")

    # Load ncu results
    ncu_path = run_dir / "p6_ncu_results.json"
    p6 = []
    if ncu_path.exists():
        with open(ncu_path, encoding="utf-8") as f:
            p6 = json.load(f)

    log.info(
        "Loaded: P2=%d P3=%d P4=%d P5=%d P6=%d runs",
        len(p2),
        len(p3),
        len(p4),
        len(p5),
        len(p6),
    )

    # Build sections
    s1 = _section_1_summary(p2, p3, p4, p5, p6)
    s2 = _section_2_kernel_comparison(exports_dir, p2, p3, p4, p5)
    s3 = _section_3_gpu_utilization(exports_dir, p2, p3, p4, p5)
    s4 = _section_4_serialization(exports_dir, p2, p3, p4, p5)
    s5 = _section_5_context_switches(exports_dir, p2, p3)
    s6 = _section_6_memory_bandwidth(exports_dir, p2, p3, p4, p5, p6)
    s7 = _section_7_wddm_queue(exports_dir, p2, p3)
    s8 = _section_8_os_runtime(exports_dir, p2, p3)
    s9 = _section_9_memory_allocation(exports_dir, p2, p3, p4, p5)
    s10 = _section_10_pytorch_vs_ollama(p2, p3, p4, p5)
    s11 = _section_11_hypothesis_verdicts(
        {
            "s2": s2,
            "s3": s3,
            "s4": s4,
            "s5": s5,
            "s6": s6,
            "s7": s7,
            "s8": s8,
            "s9": s9,
            "s10": s10,
        }
    )
    s12 = _section_12_tr130_crossval(p2, p3)

    analysis = {
        "section_01_summary": s1,
        "section_02_kernel_comparison": s2,
        "section_03_gpu_utilization": s3,
        "section_04_serialization": s4,
        "section_05_context_switches": s5,
        "section_06_memory_bandwidth": s6,
        "section_07_wddm_queue": s7,
        "section_08_os_runtime": s8,
        "section_09_memory_allocation": s9,
        "section_10_pytorch_vs_ollama": s10,
        "section_11_hypothesis_verdicts": s11,
        "section_12_tr130_crossval": s12,
    }

    # Save
    output_path = run_dir / "analysis.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(analysis, f, indent=2, default=str)
    log.info("Analysis saved: %s", output_path)

    # Log summary
    _log_summary(s1, s11)

    return analysis


def _log_summary(s1: dict, s11: dict) -> None:
    """Log analysis summary to console."""
    log.info("=" * 60)
    log.info("ANALYSIS SUMMARY (with statistical rigor)")
    log.info("=" * 60)

    for label in ["ollama_n1", "ollama_n8", "pytorch_n1", "pytorch_n8"]:
        stats = s1.get(f"{label}_tps")
        if stats:
            ci = stats.get("ci_95", [0, 0])
            log.info(
                "  %s TPS: %.2f [%.2f, %.2f] (n=%d)",
                label,
                stats["mean"],
                ci[0],
                ci[1],
                stats["n"],
            )

    log.info("-" * 60)
    # Degradation tests
    for prefix in ["ollama", "pytorch"]:
        dt = s1.get("degradation_tests", {}).get(prefix)
        if dt:
            log.info(
                "  %s N=1→N=8: delta=%.2f (p=%.4f, d=%.3f %s)",
                prefix,
                dt["delta_abs"],
                dt["p_value"],
                dt["cohens_d"],
                dt["effect_size"],
            )

    log.info("-" * 60)
    log.info("HYPOTHESIS VERDICTS:")
    for hid, v in s11.get("verdicts", {}).items():
        log.info(
            "  %s: %s (%s, %s confidence)",
            hid,
            v["verdict"],
            v["support_ratio"],
            v["confidence"],
        )

    log.info("-" * 60)
    log.info("  Primary cause: %s", s11.get("primary_cause"))

    # Attribution
    attr = s11.get("degradation_attribution", {})
    if attr:
        log.info(
            "  Ollama degradation: %.1f%%", attr.get("ollama_total_degradation_pct", 0)
        )
        log.info(
            "  PyTorch degradation: %.1f%%",
            attr.get("pytorch_total_degradation_pct", 0),
        )
        log.info(
            "  Attributable to Ollama: %.1f%%",
            attr.get("attributable_to_ollama_pct", 0),
        )
        log.info(
            "  Attributable to GPU physics: %.1f%%",
            attr.get("attributable_to_gpu_physics_pct", 0),
        )

    # Holm correction
    holm = s11.get("holm_correction", [])
    if holm:
        log.info("-" * 60)
        log.info("HOLM STEP-DOWN CORRECTION:")
        for h in holm:
            log.info(
                "  %s: p=%.4f, threshold=%.6f, sig=%s",
                h["label"],
                h["p_value"],
                h["holm_threshold"],
                h["significant_holm"],
            )

    log.info("=" * 60)
