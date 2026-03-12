"""TR129 Phase 3 — Think-Time Sweep.

Fixed N=4, think time = {0, 100, 500, 2000} ms between response and next request.
3 models × 4 think_times × 4 agents × 30 req/agent.
Shows whether inter-request delay improves scheduling.

~1,440 rows, ~30 min.
"""

from __future__ import annotations

import asyncio
import csv
import logging
from pathlib import Path

import numpy as np

from research.tr129.shared.agent_executor import run_n_agent_test
from research.tr129.shared.gpu_monitor import GpuMonitor
from research.tr129.shared.utils import generate_prompts

log = logging.getLogger("tr129.phase3")


def run_phase3(
    cfg: dict,
    run_dir: Path,
    writer: csv.DictWriter,
) -> int:
    """Execute Phase 3: think-time sweep.

    Returns number of rows written.
    """
    p3 = cfg["phase3"]
    models = cfg["models"]
    url = cfg["ollama_url"]
    max_tokens = cfg["max_new_tokens"]
    timeout = cfg.get("ollama_timeout_s", 120)
    n_agents = p3["n_agents"]
    req_per_agent = p3["requests_per_agent"]
    think_times = p3["think_times_ms"]
    seed = cfg.get("seed", 42)
    rows_written = 0

    gpu_mon = GpuMonitor(interval=cfg.get("gpu_poll_interval_s", 1.0))
    gpu_mon.start()

    try:
        for model_cfg in models:
            tag = model_cfg["ollama_tag"]
            model_name = model_cfg["name"]

            for think_ms in think_times:
                total_requests = n_agents * req_per_agent
                log.info(
                    "  P3: %s — N=%d, think=%dms, %d req/agent",
                    model_name,
                    n_agents,
                    think_ms,
                    req_per_agent,
                )

                rng = np.random.default_rng(seed)
                prompts = generate_prompts(
                    max(total_requests, 50),
                    rng=rng,
                    low=p3["prompt_tokens_low"],
                    high=p3["prompt_tokens_high"],
                )

                results = asyncio.run(
                    run_n_agent_test(
                        url=url,
                        model=tag,
                        n_agents=n_agents,
                        requests_per_agent=req_per_agent,
                        prompts=prompts,
                        think_time_ms=float(think_ms),
                        max_tokens=max_tokens,
                        timeout=timeout,
                    )
                )

                n_ok = sum(1 for r in results if r.status == "ok")
                log.info(
                    "  P3: %s think=%dms — %d/%d ok",
                    model_name,
                    think_ms,
                    n_ok,
                    len(results),
                )

                for r in results:
                    row = {
                        "phase": "p3_think_time",
                        "model": model_name,
                        "agent_id": r.agent_id,
                        "n_agents": n_agents,
                        "think_time_ms": think_ms,
                        "config_id": "",
                        "request_id": r.request_id,
                        "request_sequence": r.request_sequence,
                        "in_flight_at_submit": r.in_flight_at_submit,
                        "wall_ms": round(r.wall_ms, 2),
                        "prompt_tokens": r.prompt_tokens,
                        "completion_tokens": r.completion_tokens,
                        "prompt_eval_ms": round(r.prompt_eval_ms, 2),
                        "eval_ms": round(r.eval_ms, 2),
                        "total_duration_ms": round(r.total_duration_ms, 2),
                        "load_duration_ms": round(r.load_duration_ms, 2),
                        "gpu_tokens_per_s": round(r.gpu_tokens_per_s, 2),
                        "effective_tps": round(r.effective_tps, 2),
                        "submit_time_s": r.submit_time_s,
                        "complete_time_s": r.complete_time_s,
                        "status": r.status,
                    }
                    writer.writerow(row)
                    rows_written += 1
    finally:
        gpu_samples = gpu_mon.stop()
        if gpu_samples:
            GpuMonitor.save_csv(gpu_samples, run_dir / "gpu_phase3.csv")
            summary = GpuMonitor.summarize(gpu_samples)
            log.info(
                "  P3 GPU: %.0f°C mean, %.0f%% util mean",
                summary.get("temp_c", {}).get("mean", 0),
                summary.get("gpu_util_pct", {}).get("mean", 0),
            )

    log.info("  Phase 3 complete: %d rows", rows_written)
    return rows_written
