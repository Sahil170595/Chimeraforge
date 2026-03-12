"""TR132 cross-reference: load TR131 Ollama/PyTorch profiled data.

TR131 stores per-phase results as JSON arrays in each run directory:
  - p2_ollama_n1_results.json  — list[dict] with run_label, mean_tps, model, ...
  - p3_ollama_n8_results.json
  - p4_pytorch_n1_results.json
  - p5_pytorch_n8_results.json

Parsed trace data lives separately in exports/{run_label}_parsed.json.

This module loads both and extracts the exact metrics needed for the 4-way
comparison (vLLM vs TGI vs Ollama vs PyTorch).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

log = logging.getLogger("tr132.cross_reference")

# ── Path to TR131 results ────────────────────────────────────────────
_DIR = Path(__file__).resolve().parent
_REPO = _DIR.parents[2]
TR131_RESULTS = _REPO / "research" / "tr131" / "results"


def find_latest_tr131_run(results_dir: str | Path | None = None) -> Path | None:
    """Find the most recent TR131 run directory."""
    results_dir = Path(results_dir) if results_dir else TR131_RESULTS
    if not results_dir.is_dir():
        log.warning("TR131 results dir not found: %s", results_dir)
        return None
    candidates = [
        p
        for p in results_dir.iterdir()
        if p.is_dir() and len(p.name) == 15 and p.name[8] == "_"
    ]
    if not candidates:
        log.warning("No TR131 run directories found in %s", results_dir)
        return None
    return max(candidates, key=lambda p: p.name)


def _load_json(path: Path):
    """Load JSON file, return None on failure."""
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        log.warning("Failed to load %s: %s", path, e)
        return None


def _load_parsed_trace(exports_dir: Path, run_label: str) -> dict | None:
    """Load a parsed trace JSON from the exports directory."""
    candidates = list(exports_dir.glob(f"*{run_label}*_parsed.json"))
    if not candidates:
        # Also try without _parsed suffix — some runs store differently
        candidates = list(exports_dir.glob(f"{run_label}*.json"))
    if candidates:
        return _load_json(candidates[0])
    return None


def load_tr131_data(
    results_dir: str | Path | None = None,
    run_dir: Path | None = None,
) -> dict:
    """Load TR131 Ollama and PyTorch profiled data for cross-reference.

    Returns
    -------
    dict with keys: ollama_n1, ollama_n8, pytorch_n1, pytorch_n8 (each a
    list[dict] of per-run results), plus manifest, run_dir, exports_dir, status.
    """
    result = {
        "status": "not_found",
        "run_dir": None,
        "exports_dir": None,
        "manifest": None,
        "ollama_n1": None,
        "ollama_n8": None,
        "pytorch_n1": None,
        "pytorch_n8": None,
    }

    if run_dir is None:
        run_dir = find_latest_tr131_run(results_dir)
    if run_dir is None:
        return result

    run_dir = Path(run_dir)
    result["run_dir"] = str(run_dir)
    log.info("Loading TR131 data from: %s", run_dir)

    # Load manifest
    result["manifest"] = _load_json(run_dir / "manifest.json")

    # Exports directory for parsed traces
    exports_dir = run_dir / "exports"
    if exports_dir.is_dir():
        result["exports_dir"] = str(exports_dir)

    # TR131 phase result files are JSON arrays.
    phase_mapping = {
        "ollama_n1": ["p2_ollama_n1", "p2_results"],
        "ollama_n8": ["p3_ollama_n8", "p3_results"],
        "pytorch_n1": ["p4_pytorch_n1", "p4_results"],
        "pytorch_n8": ["p5_pytorch_n8", "p5_results"],
    }

    loaded_count = 0
    for key, patterns in phase_mapping.items():
        for pattern in patterns:
            candidates = list(run_dir.glob(f"*{pattern}*.json"))
            if candidates:
                data = _load_json(candidates[0])
                if data is not None:
                    result[key] = data
                    loaded_count += 1
                    log.info(
                        "  Loaded %s: %s (%d runs)",
                        key,
                        candidates[0].name,
                        len(data) if isinstance(data, list) else 1,
                    )
                    break

    if loaded_count > 0:
        result["status"] = "partial" if loaded_count < 4 else "complete"
    log.info(
        "TR131 cross-reference: %d/4 phases loaded (%s)", loaded_count, result["status"]
    )

    return result


def extract_tr131_metrics(tr131_data: dict) -> dict:
    """Extract structured per-model metrics from TR131 data.

    TR131 phase result files are JSON arrays, each entry is one profiling run
    with keys: run_label, model, n_agents/n_threads, repetition, mean_tps,
    mean_wall_ms, trace_size_mb, requests_total, requests_ok.

    Parsed trace data (kernel counts, GPU utilization, memory time) is loaded
    from exports/{run_label}_parsed.json.

    Returns
    -------
    dict keyed by "backend_nN" (e.g. "ollama_n1") containing:
        {model_name: [rep_dict, ...]}
    where each rep_dict has: mean_tps, kernel_count, gpu_time_ms,
    gpu_utilization_pct, max_concurrent_kernels, mem_time_ms, etc.
    """
    metrics = {}
    exports_dir = tr131_data.get("exports_dir")
    if exports_dir:
        exports_dir = Path(exports_dir)

    phase_keys = {
        "ollama_n1": ("ollama", 1),
        "ollama_n8": ("ollama", 8),
        "pytorch_n1": ("pytorch", 1),
        "pytorch_n8": ("pytorch", 8),
    }

    for data_key, (backend, n_agents) in phase_keys.items():
        phase_data = tr131_data.get(data_key)
        if phase_data is None:
            continue

        # Normalize to list
        runs = phase_data if isinstance(phase_data, list) else [phase_data]

        # Group by model
        by_model: dict[str, list[dict]] = {}
        for run in runs:
            model = run.get("model", "unknown")
            run_label = run.get("run_label", "")

            rep = {
                "backend": backend,
                "n_agents": n_agents,
                "repetition": run.get("repetition", 0),
                "mean_tps": run.get("mean_tps", 0),
                "mean_wall_ms": run.get("mean_wall_ms", 0),
                "requests_ok": run.get("requests_ok", 0),
                "requests_total": run.get("requests_total", 0),
                "trace_size_mb": run.get("trace_size_mb", 0),
                "profile_wall_s": run.get("profile_wall_s", 0),
            }

            # Load parsed trace data if exports_dir exists
            if exports_dir and run_label:
                parsed = _load_parsed_trace(exports_dir, run_label)
                if parsed:
                    kern_sum = parsed.get("cuda_gpu_kern_sum", {})
                    exec_trace = parsed.get("cuda_kern_exec_trace", {})
                    mem_sum = parsed.get("cuda_gpu_mem_time_sum", {})

                    rep["kernel_count"] = kern_sum.get("total_instances", 0)
                    rep["gpu_time_ms"] = kern_sum.get("total_gpu_time_ms", 0)
                    rep["kernel_classification"] = kern_sum.get(
                        "kernel_classification", {}
                    )
                    rep["top_kernels"] = [
                        {
                            "name": k["name"][:80],
                            "time_ms": k.get("total_time_ms", 0),
                            "instances": k.get("instances", 0),
                        }
                        for k in kern_sum.get("top_10", [])[:5]
                    ]

                    rep["n_launches"] = exec_trace.get("n_launches", 0)
                    rep["gpu_active_ms"] = exec_trace.get("gpu_active_ms", 0)
                    rep["gpu_utilization_pct"] = exec_trace.get(
                        "gpu_utilization_pct", 0
                    )
                    rep["max_concurrent_kernels"] = exec_trace.get(
                        "max_concurrent_kernels", 0
                    )

                    rep["mem_time_ms"] = mem_sum.get("total_time_ms", 0)
                    rep["mem_ops"] = mem_sum.get("total_ops", 0)

                    rep["has_trace_data"] = True
                else:
                    rep["has_trace_data"] = False
            else:
                rep["has_trace_data"] = False

            # Compute per-token metrics where possible
            total_tokens = rep["requests_ok"] * 128  # Approximate: max_new_tokens
            if rep.get("mean_tps", 0) > 0 and rep.get("profile_wall_s", 0) > 0:
                # Better estimate: mean_tps * profile_wall_s gives total tokens
                total_tokens = int(rep["mean_tps"] * rep["profile_wall_s"])
            rep["total_tokens_est"] = total_tokens

            if total_tokens > 0 and rep.get("kernel_count", 0) > 0:
                rep["kernels_per_token"] = rep["kernel_count"] / total_tokens
            if total_tokens > 0 and rep.get("mem_time_ms", 0) > 0:
                rep["mem_time_per_token_ms"] = rep["mem_time_ms"] / total_tokens

            by_model.setdefault(model, []).append(rep)

        key = f"{backend}_n{n_agents}"
        metrics[key] = by_model
        log.info(
            "  Extracted %s: %d models, %d total runs",
            key,
            len(by_model),
            sum(len(v) for v in by_model.values()),
        )

    return metrics


def extract_tr131_degradation(tr131_metrics: dict) -> dict:
    """Extract per-agent TPS degradation ratios from TR131 data.

    Returns {model: {backend: {"n1_mean_tps": X, "n8_mean_tps": Y,
                                "degradation_pct": Z}}}
    """
    degradation = {}

    for backend in ["ollama", "pytorch"]:
        n1_key = f"{backend}_n1"
        n8_key = f"{backend}_n8"
        n1_data = tr131_metrics.get(n1_key, {})
        n8_data = tr131_metrics.get(n8_key, {})

        for model in set(list(n1_data.keys()) + list(n8_data.keys())):
            n1_reps = n1_data.get(model, [])
            n8_reps = n8_data.get(model, [])

            n1_tps = [r["mean_tps"] for r in n1_reps if r.get("mean_tps", 0) > 0]
            n8_tps = [r["mean_tps"] for r in n8_reps if r.get("mean_tps", 0) > 0]

            if n1_tps and n8_tps:
                import numpy as np

                n1_mean = float(np.mean(n1_tps))
                n8_mean = float(np.mean(n8_tps))
                deg = (1 - n8_mean / n1_mean) * 100 if n1_mean > 0 else 0

                degradation.setdefault(model, {})[backend] = {
                    "n1_mean_tps": round(n1_mean, 2),
                    "n8_mean_tps": round(n8_mean, 2),
                    "degradation_pct": round(deg, 1),
                    "n1_reps": len(n1_tps),
                    "n8_reps": len(n8_tps),
                }

    return degradation
