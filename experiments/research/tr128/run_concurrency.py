"""TR128 Phase 2 — Concurrency & Saturation Sweep.

THE core experiment.  Sweeps OLLAMA_NUM_PARALLEL x arrival_rate x model.
Tests where reality diverges from M/D/1 queueing predictions.

The caller (run.py) restarts Ollama with different OLLAMA_NUM_PARALLEL
values between sub-sweeps.  This module receives num_parallel as a
parameter and runs one sweep at a time.

3 models x 5 rates x 30 req = 450 rows per parallelism level.
With 3 parallelism levels: 1350 total rows.
"""

from __future__ import annotations

import asyncio
import csv
import logging
from pathlib import Path

import numpy as np

from research.tr128.shared.gpu_monitor import GpuMonitor
from research.tr128.shared.load_generator import (
    poisson_arrivals,
    run_load_test,
)
from research.tr128.shared.utils import (
    generate_ollama_prompt,
    generate_prompt_lengths,
)

log = logging.getLogger("tr128.phase2")


def run_phase2_sweep(
    cfg: dict,
    run_dir: Path,
    writer: csv.DictWriter,
    num_parallel: int,
) -> int:
    """Execute one concurrency sweep at a given OLLAMA_NUM_PARALLEL level.

    Called once per parallelism level by the orchestrator, which handles
    restarting Ollama between calls.

    Returns number of rows written.
    """
    p2 = cfg["phase2"]
    models = cfg["models"]
    url = cfg["ollama_url"]
    max_tokens = cfg["max_new_tokens"]
    timeout = cfg.get("ollama_timeout_s", 120)
    n_per = p2["requests_per_rate"]
    seed = cfg.get("seed", 42)
    rows_written = 0

    gpu_mon = GpuMonitor(interval=cfg.get("gpu_poll_interval_s", 1.0))
    gpu_mon.start()

    try:
        for model_cfg in models:
            tag = model_cfg["ollama_tag"]
            model_name = model_cfg["name"]

            for rate in p2["arrival_rates"]:
                log.info(
                    "  P2: %s / NP=%d / rate=%.1f rps / %d requests",
                    model_name,
                    num_parallel,
                    rate,
                    n_per,
                )

                rng = np.random.default_rng(seed)
                lengths = generate_prompt_lengths(
                    n_per,
                    "uniform",
                    p2["prompt_tokens_low"],
                    p2["prompt_tokens_high"],
                    rng=rng,
                )
                prompts = [generate_ollama_prompt(l) for l in lengths]
                arrival_gen = poisson_arrivals(n_per, rate, rng=rng)

                results = asyncio.run(
                    run_load_test(
                        url,
                        tag,
                        prompts,
                        arrival_gen,
                        executor="batch",
                        max_tokens=max_tokens,
                        timeout=timeout,
                    )
                )

                n_ok = sum(1 for r in results if r.status == "ok")
                if n_ok < len(results):
                    log.warning(
                        "  P2: %s NP=%d rate=%.1f — %d/%d ok",
                        model_name,
                        num_parallel,
                        rate,
                        n_ok,
                        len(results),
                    )

                for r in results:
                    row = {
                        "phase": "p2_concurrency",
                        "model": model_name,
                        "num_parallel": num_parallel,
                        "arrival_pattern": "poisson",
                        "arrival_rate_rps": rate,
                        "prompt_distribution": "uniform",
                        "response_mode": "batch",
                        "request_id": r.request_id,
                        "queue_depth_at_submit": r.queue_depth_at_submit,
                        "wall_ms": round(r.wall_ms, 2),
                        "ttft_ms": "",
                        "ichunk_mean_ms": "",
                        "ichunk_p95_ms": "",
                        "ichunk_jitter_cv": "",
                        "prompt_tokens": r.prompt_tokens,
                        "completion_tokens": r.completion_tokens,
                        "prompt_eval_ms": round(r.prompt_eval_ms, 2),
                        "eval_ms": round(r.eval_ms, 2),
                        "total_duration_ms": round(r.total_duration_ms, 2),
                        "load_duration_ms": round(r.load_duration_ms, 2),
                        "tokens_per_s": round(r.tokens_per_s, 2),
                        "turn_number": "",
                        "conversation_id": "",
                        "context_strategy": "",
                        "status": r.status,
                    }
                    writer.writerow(row)
                    rows_written += 1
    finally:
        gpu_samples = gpu_mon.stop()
        if gpu_samples:
            gpu_path = run_dir / f"gpu_phase2_np{num_parallel}.csv"
            GpuMonitor.save_csv(gpu_samples, gpu_path)
            summary = GpuMonitor.summarize(gpu_samples)
            log.info(
                "  P2 NP=%d GPU: %.0f°C peak, %.0f%% util mean, throttle=%s",
                num_parallel,
                summary.get("temp_c", {}).get("max", 0),
                summary.get("gpu_util_pct", {}).get("mean", 0),
                summary.get("thermal_throttle", {}).get("detected", False),
            )

    log.info("  Phase 2 (NP=%d) complete: %d rows", num_parallel, rows_written)
    return rows_written
