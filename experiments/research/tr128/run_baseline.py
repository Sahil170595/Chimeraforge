"""TR128 Phase 1 — Baseline Characterization.

Serial, no concurrency.  Establishes per-model service time distribution
at zero load, which predicts theoretical saturation via M/D/1 queueing.

3 models x 50 requests = 150 rows.  GPU monitoring captures idle→active
thermal profile.
"""

from __future__ import annotations

import asyncio
import csv
import logging
from pathlib import Path

import numpy as np

from research.tr128.shared.gpu_monitor import GpuMonitor
from research.tr128.shared.load_generator import (
    RequestResult,
    execute_batch_request,
)
from research.tr128.shared.utils import (
    generate_ollama_prompt,
    generate_prompt_lengths,
)

log = logging.getLogger("tr128.phase1")

import httpx


async def _serial_baseline(
    url: str,
    model_tag: str,
    prompts: list[str],
    max_tokens: int,
    timeout: float,
) -> list[RequestResult]:
    """Execute requests one-at-a-time (queue depth always 0)."""
    results: list[RequestResult] = []
    async with httpx.AsyncClient() as client:
        for idx, prompt in enumerate(prompts):
            r = await execute_batch_request(
                client,
                url,
                model_tag,
                prompt,
                max_tokens,
                timeout,
            )
            r.request_id = idx
            r.queue_depth_at_submit = 0
            results.append(r)
            if r.status != "ok":
                log.warning("  Baseline request %d: %s", idx, r.status)
    return results


def run_phase1(
    cfg: dict,
    run_dir: Path,
    writer: csv.DictWriter,
) -> int:
    """Execute Phase 1: serial baseline characterization.

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
            log.info("  P1: %s — %d serial requests", model_name, n_per)

            rng = np.random.default_rng(seed)
            lengths = generate_prompt_lengths(
                n_per,
                "uniform",
                p1["prompt_tokens_low"],
                p1["prompt_tokens_high"],
                rng=rng,
            )
            prompts = [generate_ollama_prompt(l) for l in lengths]

            results = asyncio.run(
                _serial_baseline(
                    url,
                    tag,
                    prompts,
                    max_tokens,
                    timeout,
                )
            )

            n_ok = sum(1 for r in results if r.status == "ok")
            log.info("  P1: %s — %d/%d ok", model_name, n_ok, len(results))

            for r in results:
                row = {
                    "phase": "p1_baseline",
                    "model": model_name,
                    "num_parallel": 1,
                    "arrival_pattern": "serial",
                    "arrival_rate_rps": 0,
                    "prompt_distribution": "uniform",
                    "response_mode": "batch",
                    "request_id": r.request_id,
                    "queue_depth_at_submit": 0,
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
            GpuMonitor.save_csv(gpu_samples, run_dir / "gpu_phase1.csv")
            summary = GpuMonitor.summarize(gpu_samples)
            log.info(
                "  P1 GPU: %.0f°C mean, %.0f%% util mean",
                summary.get("temp_c", {}).get("mean", 0),
                summary.get("gpu_util_pct", {}).get("mean", 0),
            )

    log.info("  Phase 1 complete: %d rows", rows_written)
    return rows_written
