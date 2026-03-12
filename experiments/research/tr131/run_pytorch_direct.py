"""TR131 Phase 4-5: Profile direct PyTorch inference at N=1 and N=8.

No serving stack — loads model via transformers, calls model.generate().
nsys wraps the entire Python process for full CUDA kernel visibility.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
import subprocess
import time

from research.tr131.shared.nsys_driver import NsysDriver
from research.tr131.shared.trace_parser import parse_all_reports
from research.tr131.shared.utils import (
    NSYS_PATH,
    NSYS_REPORTS,
)

log = logging.getLogger("tr131.pytorch_direct")

# Path to the Python executable (nsys will launch this)
_PYTHON = subprocess.check_output(
    ["python", "-c", "import sys; print(sys.executable)"],
    text=True,
).strip()


def _pytorch_worker_script(
    hf_id: str,
    n_threads: int,
    requests_per_thread: int,
    max_new_tokens: int,
    output_json: str,
) -> str:
    """Generate a standalone Python script for nsys to profile.

    nsys needs to wrap a process, so we generate a script that:
    1. Loads the model
    2. Runs N threads of inference
    3. Saves results to JSON
    """
    return f"""
import json
import sys
import time
sys.path.insert(0, r"{Path(__file__).resolve().parents[2]}")

from research.tr131.shared.pytorch_inference import (
    PyTorchInferenceEngine, run_single_thread, run_concurrent,
)
from research.tr131.shared.utils import generate_prompts

engine = PyTorchInferenceEngine("{hf_id}", max_new_tokens={max_new_tokens})
engine.load()

# Warmup
prompts = generate_prompts(3, low=50, high=80)
for p in prompts:
    engine.generate_one(p)

# Actual inference
n_threads = {n_threads}
requests_per_thread = {requests_per_thread}
total = n_threads * requests_per_thread
prompts = generate_prompts(total)

if n_threads == 1:
    results = run_single_thread(engine, prompts[:requests_per_thread])
else:
    prompts_per_thread = []
    for i in range(n_threads):
        start = i * requests_per_thread
        prompts_per_thread.append(prompts[start:start + requests_per_thread])
    results = run_concurrent(engine, n_threads, prompts_per_thread)

# Save
out = []
for r in results:
    out.append({{
        "thread_id": r.thread_id,
        "request_seq": r.request_seq,
        "wall_ms": r.wall_ms,
        "prompt_tokens": r.prompt_tokens,
        "completion_tokens": r.completion_tokens,
        "effective_tps": r.effective_tps,
        "status": r.status,
    }})

with open(r"{output_json}", "w") as f:
    json.dump(out, f, indent=2)

engine.unload()
print(f"Done: {{len(out)}} results saved")
"""


def run_pytorch_profiled(
    cfg: dict,
    run_dir: Path,
    n_threads: int,
    phase: str,
) -> list[dict]:
    """Profile direct PyTorch inference at a given concurrency level.

    Args:
        cfg: Full config dict
        run_dir: Run directory
        n_threads: Number of concurrent threads (1 or 8)
        phase: Phase identifier (e.g., "p4_pytorch_n1")

    Returns:
        List of per-run result dicts.
    """
    traces_dir = run_dir / "traces"
    exports_dir = run_dir / "exports"
    scripts_dir = run_dir / "scripts"
    traces_dir.mkdir(parents=True, exist_ok=True)
    exports_dir.mkdir(parents=True, exist_ok=True)
    scripts_dir.mkdir(parents=True, exist_ok=True)

    # Config from phase
    phase_cfg = cfg.get("phase4", {}) if n_threads == 1 else cfg.get("phase5", {})

    requests_per_thread = phase_cfg.get(
        "requests_per_thread", 5 if n_threads == 1 else 3
    )
    reps = phase_cfg.get("repetitions", 3)
    duration_s = phase_cfg.get("profile_duration_s", 60)
    max_tokens = cfg.get("max_new_tokens", 128)

    nsys = NsysDriver(str(NSYS_PATH), cfg.get("nsys", {}))
    all_results = []

    for model in cfg["models"]:
        model_name = model["name"]
        hf_id = model["hf_id"]

        for rep in range(reps):
            run_label = f"{phase}_{model_name}_rep{rep}"
            log.info("--- %s (N=%d) ---", run_label, n_threads)

            # Generate worker script
            results_json = run_dir / f"{run_label}_inference.json"
            script_content = _pytorch_worker_script(
                hf_id=hf_id,
                n_threads=n_threads,
                requests_per_thread=requests_per_thread,
                max_new_tokens=max_tokens,
                output_json=str(results_json).replace("\\", "/"),
            )
            script_path = scripts_dir / f"{run_label}.py"
            script_path.write_text(script_content, encoding="utf-8")

            # Profile with nsys
            t0 = time.perf_counter()
            try:
                rep_path = nsys.profile(
                    target_cmd=[_PYTHON, str(script_path)],
                    output_path=traces_dir / run_label,
                    duration_s=duration_s,
                )
                profile_wall_s = time.perf_counter() - t0
            except Exception as e:
                log.error("Profile failed for %s: %s", run_label, e)
                continue

            # Extract stats
            try:
                nsys.stats_csv(rep_path, NSYS_REPORTS, exports_dir)
            except Exception as e:
                log.warning("Stats extraction failed: %s", e)

            # Parse traces
            parsed = parse_all_reports(exports_dir, run_label)

            # Load inference results
            inference_results = []
            if results_json.exists():
                with open(results_json, encoding="utf-8") as f:
                    inference_results = json.load(f)

            ok_results = [r for r in inference_results if r.get("status") == "ok"]
            tps_values = [r["effective_tps"] for r in ok_results]

            result = {
                "run_label": run_label,
                "phase": phase,
                "model": model_name,
                "hf_id": hf_id,
                "n_threads": n_threads,
                "repetition": rep,
                "profile_wall_s": round(profile_wall_s, 1),
                "trace_file": str(rep_path),
                "trace_size_mb": round(rep_path.stat().st_size / 1e6, 1),
                "requests_total": len(inference_results),
                "requests_ok": len(ok_results),
                "mean_tps": (
                    round(sum(tps_values) / len(tps_values), 2) if tps_values else 0
                ),
                "mean_wall_ms": (
                    round(sum(r["wall_ms"] for r in ok_results) / len(ok_results), 1)
                    if ok_results
                    else 0
                ),
                "parsed_traces": parsed,
            }

            # Log key metrics
            kern = parsed.get("cuda_gpu_kern_sum", {})
            exec_trace = parsed.get("cuda_kern_exec_trace", {})
            log.info(
                "  TPS=%.1f  kernels=%d  GPU_util=%.1f%%  max_concurrent=%d",
                result["mean_tps"],
                kern.get("total_instances", 0),
                exec_trace.get("gpu_utilization_pct", 0),
                exec_trace.get("max_concurrent_kernels", 0),
            )

            all_results.append(result)
            time.sleep(3)  # Cooldown

    # Save phase results
    save_results = []
    for r in all_results:
        save_r = {k: v for k, v in r.items() if k != "parsed_traces"}
        save_results.append(save_r)
    with open(run_dir / f"{phase}_results.json", "w", encoding="utf-8") as f:
        json.dump(save_results, f, indent=2, default=str)

    # Save parsed traces separately
    for r in all_results:
        trace_data_path = exports_dir / f"{r['run_label']}_parsed.json"
        with open(trace_data_path, "w", encoding="utf-8") as f:
            json.dump(r.get("parsed_traces", {}), f, indent=2, default=str)

    return all_results
