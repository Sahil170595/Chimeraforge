"""TR129 Phase 1 — Single-Agent Baseline.

N=1 closed-loop, 50 requests per model, 3 models.
Establishes reference per-agent throughput for efficiency calculations.
Cross-validates with TR128 Phase 1.

3 models × 50 requests = 150 rows, ~5 min.
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

log = logging.getLogger("tr129.phase1")


def run_phase1(
    cfg: dict,
    run_dir: Path,
    writer: csv.DictWriter,
) -> int:
    """Execute Phase 1: single-agent baseline.

    Returns number of rows written.
    """
    p1 = cfg["phase1"]
    models = cfg["models"]
    url = cfg["ollama_url"]
    max_tokens = cfg["max_new_tokens"]
    timeout = cfg.get("ollama_timeout_s", 120)
    n_per = p1["requests_per_model"]
    seed = cfg.get("seed", 42)
    rows_written = 0

    gpu_mon = GpuMonitor(interval=cfg.get("gpu_poll_interval_s", 1.0))
    gpu_mon.start()

    try:
        for model_cfg in models:
            tag = model_cfg["ollama_tag"]
            model_name = model_cfg["name"]
            log.info("  P1: %s — %d serial requests (N=1)", model_name, n_per)

            rng = np.random.default_rng(seed)
            prompts = generate_prompts(
                n_per,
                rng=rng,
                low=p1["prompt_tokens_low"],
                high=p1["prompt_tokens_high"],
            )

            results = asyncio.run(
                run_n_agent_test(
                    url=url,
                    model=tag,
                    n_agents=1,
                    requests_per_agent=n_per,
                    prompts=prompts,
                    think_time_ms=0.0,
                    max_tokens=max_tokens,
                    timeout=timeout,
                )
            )

            n_ok = sum(1 for r in results if r.status == "ok")
            log.info("  P1: %s — %d/%d ok", model_name, n_ok, len(results))

            for r in results:
                row = {
                    "phase": "p1_baseline",
                    "model": model_name,
                    "agent_id": r.agent_id,
                    "n_agents": 1,
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
    finally:
        gpu_samples = gpu_mon.stop()
        if gpu_samples:
            GpuMonitor.save_csv(gpu_samples, run_dir / "gpu_phase1.csv")
            summary = GpuMonitor.summarize(gpu_samples)
            log.info(
                "  P1 GPU: %.0f°C mean, %.0f%% util mean",
                summary.get("temp_c", {}).get("mean", 0),
                summary.get("gpu_util_pct", {}).get("mean", 0),
            )

    log.info("  Phase 1 complete: %d rows", rows_written)
    return rows_written
