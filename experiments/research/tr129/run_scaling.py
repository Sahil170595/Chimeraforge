"""TR129 Phase 2 — Homogeneous N-Agent Scaling (CORE).

N = {1, 2, 3, 4, 5, 6, 7, 8} concurrent closed-loop agents → 1 Ollama instance.
30 requests per agent per config.
3 models × 8 N-levels = 24 configs.

8 data points per model enables meaningful curve fitting (not 4-point interpolation).
Cooldown between configs prevents thermal carry-over.

Measures: per-agent effective_tps, total effective throughput, efficiency η(N),
fairness (Jain's).
~2,700 rows, ~60 min.
"""

from __future__ import annotations

import asyncio
import csv
import logging
from pathlib import Path
import time

import numpy as np

from research.tr129.shared.agent_executor import run_n_agent_test
from research.tr129.shared.gpu_monitor import GpuMonitor
from research.tr129.shared.utils import generate_prompts

log = logging.getLogger("tr129.phase2")


def run_phase2(
    cfg: dict,
    run_dir: Path,
    writer: csv.DictWriter,
) -> int:
    """Execute Phase 2: N-agent scaling sweep.

    Returns number of rows written.
    """
    p2 = cfg["phase2"]
    models = cfg["models"]
    url = cfg["ollama_url"]
    max_tokens = cfg["max_new_tokens"]
    timeout = cfg.get("ollama_timeout_s", 120)
    req_per_agent = p2["requests_per_agent"]
    n_levels = p2["n_agent_levels"]
    cooldown_s = p2.get("cooldown_between_configs_s", 5)
    seed = cfg.get("seed", 42)
    rows_written = 0

    gpu_mon = GpuMonitor(interval=cfg.get("gpu_poll_interval_s", 1.0))
    gpu_mon.start()

    try:
        for model_cfg in models:
            tag = model_cfg["ollama_tag"]
            model_name = model_cfg["name"]

            for level_idx, n_agents in enumerate(n_levels):
                total_requests = n_agents * req_per_agent
                log.info(
                    "  P2: %s — N=%d agents, %d req/agent (%d total)",
                    model_name,
                    n_agents,
                    req_per_agent,
                    total_requests,
                )

                rng = np.random.default_rng(seed)
                prompts = generate_prompts(
                    max(total_requests, 50),
                    rng=rng,
                    low=p2["prompt_tokens_low"],
                    high=p2["prompt_tokens_high"],
                )

                results = asyncio.run(
                    run_n_agent_test(
                        url=url,
                        model=tag,
                        n_agents=n_agents,
                        requests_per_agent=req_per_agent,
                        prompts=prompts,
                        think_time_ms=0.0,
                        max_tokens=max_tokens,
                        timeout=timeout,
                    )
                )

                n_ok = sum(1 for r in results if r.status == "ok")
                log.info(
                    "  P2: %s N=%d — %d/%d ok",
                    model_name,
                    n_agents,
                    n_ok,
                    len(results),
                )

                for r in results:
                    row = {
                        "phase": "p2_scaling",
                        "model": model_name,
                        "agent_id": r.agent_id,
                        "n_agents": n_agents,
                        "think_time_ms": 0,
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

                # Cooldown between N-level configs to prevent thermal carry-over
                if level_idx < len(n_levels) - 1 and cooldown_s > 0:
                    log.info("  P2: cooldown %ds before next config", cooldown_s)
                    time.sleep(cooldown_s)

    finally:
        gpu_samples = gpu_mon.stop()
        if gpu_samples:
            GpuMonitor.save_csv(gpu_samples, run_dir / "gpu_phase2.csv")
            summary = GpuMonitor.summarize(gpu_samples)
            log.info(
                "  P2 GPU: %.0f°C mean, %.0f%% util mean",
                summary.get("temp_c", {}).get("mean", 0),
                summary.get("gpu_util_pct", {}).get("mean", 0),
            )

    log.info("  Phase 2 complete: %d rows", rows_written)
    return rows_written
