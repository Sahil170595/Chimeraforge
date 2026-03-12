"""TR131 Phase 2-3: Profile Ollama at N=1 and N=8.

nsys wraps the Ollama server process.
A separate Python thread sends HTTP requests.
"""

from __future__ import annotations

import contextlib
import json
import logging
from pathlib import Path
import subprocess
from threading import Thread
import time

from research.tr131.shared.nsys_driver import NsysDriver
from research.tr131.shared.request_driver import (
    send_requests,
    wait_ollama_ready,
    warmup,
)
from research.tr131.shared.trace_parser import parse_all_reports
from research.tr131.shared.utils import (
    NSYS_PATH,
    NSYS_REPORTS,
    generate_prompts,
)

log = logging.getLogger("tr131.ollama_profiled")


def _stop_ollama() -> None:
    """Stop any running Ollama process (including tray app)."""
    with contextlib.suppress(Exception):
        subprocess.run(
            [
                "powershell",
                "-Command",
                "Get-Process | Where-Object { $_.ProcessName -like '*ollama*' } "
                "| Stop-Process -Force -ErrorAction SilentlyContinue",
            ],
            capture_output=True,
            timeout=15,
        )
    time.sleep(3)


def _request_thread(
    model_tag: str,
    n_agents: int,
    requests_per_agent: int,
    prompts: list[str],
    max_tokens: int,
    results_holder: list,
) -> None:
    """Background thread: wait for Ollama, warmup, send requests."""
    if not wait_ollama_ready(timeout_s=30):
        log.error("Ollama not ready")
        return

    warmup(model_tag, n=3, max_tokens=32)
    log.info("Sending %d agents × %d requests...", n_agents, requests_per_agent)

    results = send_requests(
        n_agents=n_agents,
        requests_per_agent=requests_per_agent,
        model_tag=model_tag,
        prompts=prompts,
        max_tokens=max_tokens,
    )
    results_holder.extend(results)


def run_ollama_profiled(
    cfg: dict,
    run_dir: Path,
    n_agents: int,
    phase: str,
) -> list[dict]:
    """Profile Ollama at a given concurrency level.

    Args:
        cfg: Full config dict
        run_dir: Run directory (contains traces/ and exports/)
        n_agents: Number of concurrent agents (1 or 8)
        phase: Phase identifier (e.g., "p2_ollama_n1")

    Returns:
        List of per-run result dicts with parsed trace data + request timing.
    """
    traces_dir = run_dir / "traces"
    exports_dir = run_dir / "exports"
    traces_dir.mkdir(parents=True, exist_ok=True)
    exports_dir.mkdir(parents=True, exist_ok=True)

    # Determine config from phase
    phase_cfg = cfg.get("phase2", {}) if n_agents == 1 else cfg.get("phase3", {})

    requests_per_agent = phase_cfg.get("requests_per_agent", 5 if n_agents == 1 else 3)
    reps = phase_cfg.get("repetitions", 3)
    duration_s = phase_cfg.get("profile_duration_s", 30)
    max_tokens = cfg.get("max_new_tokens", 128)

    nsys = NsysDriver(str(NSYS_PATH), cfg.get("nsys", {}))
    all_results = []

    for model in cfg["models"]:
        model_name = model["name"]
        model_tag = model["ollama_tag"]

        for rep in range(reps):
            run_label = f"{phase}_{model_name}_rep{rep}"
            log.info("--- %s (N=%d) ---", run_label, n_agents)

            # Stop existing Ollama
            _stop_ollama()

            # Generate prompts
            total_requests = n_agents * requests_per_agent
            prompts = generate_prompts(total_requests)

            # Start request thread
            request_results: list = []
            sender = Thread(
                target=_request_thread,
                args=(
                    model_tag,
                    n_agents,
                    requests_per_agent,
                    prompts,
                    max_tokens,
                    request_results,
                ),
                daemon=True,
            )

            # Profile
            t0 = time.perf_counter()
            try:
                sender.start()
                rep_path = nsys.profile(
                    target_cmd=["ollama", "serve"],
                    output_path=traces_dir / run_label,
                    duration_s=duration_s,
                    extra_flags=["--kill", "true"],
                )
                sender.join(timeout=10)
                profile_wall_s = time.perf_counter() - t0
            except Exception as e:
                log.error("Profile failed for %s: %s", run_label, e)
                _stop_ollama()
                continue

            # Extract stats
            try:
                nsys.stats_csv(rep_path, NSYS_REPORTS, exports_dir)
            except Exception as e:
                log.warning("Stats extraction failed: %s", e)

            # Parse
            parsed = parse_all_reports(exports_dir, run_label)

            # Compile results
            ok_requests = [r for r in request_results if r.status == "ok"]
            tps_values = [r.effective_tps for r in ok_requests]

            result = {
                "run_label": run_label,
                "phase": phase,
                "model": model_name,
                "n_agents": n_agents,
                "repetition": rep,
                "profile_wall_s": round(profile_wall_s, 1),
                "trace_file": str(rep_path),
                "trace_size_mb": round(rep_path.stat().st_size / 1e6, 1),
                "requests_total": len(request_results),
                "requests_ok": len(ok_requests),
                "mean_tps": (
                    round(sum(tps_values) / len(tps_values), 2) if tps_values else 0
                ),
                "mean_wall_ms": (
                    round(sum(r.wall_ms for r in ok_requests) / len(ok_requests), 1)
                    if ok_requests
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
            _stop_ollama()
            time.sleep(3)  # Cooldown

    # Save phase results
    save_results = []
    for r in all_results:
        save_r = {k: v for k, v in r.items() if k != "parsed_traces"}
        save_results.append(save_r)
    with open(run_dir / f"{phase}_results.json", "w", encoding="utf-8") as f:
        json.dump(save_results, f, indent=2, default=str)

    # Save parsed trace data separately (large)
    for r in all_results:
        trace_data_path = exports_dir / f"{r['run_label']}_parsed.json"
        with open(trace_data_path, "w", encoding="utf-8") as f:
            json.dump(r.get("parsed_traces", {}), f, indent=2, default=str)

    return all_results
