"""TR128 Phase 3 — Thermal Stability Under Sustained Load.

Holds at ~80% of estimated saturation rate for a fixed duration per model.
Detects whether throughput degrades over time due to GPU thermal throttling.

The key output is GPU metrics over time — temperature, clock speed, power —
correlated with per-request latency.  If clock drops while temp rises,
that's thermal throttling causing real performance degradation.

3 models x 180s = ~9 min active load.
"""

from __future__ import annotations

import asyncio
import csv
import logging
from pathlib import Path

import numpy as np

from research.tr128.shared.gpu_monitor import GpuMonitor
from research.tr128.shared.load_generator import (
    run_load_test,
    timed_periodic_arrivals,
)
from research.tr128.shared.utils import (
    generate_ollama_prompt,
    generate_prompt_lengths,
)

log = logging.getLogger("tr128.phase3")


def _estimate_saturation_rate(
    cfg: dict,
    baseline_results_by_model: dict[str, float] | None,
) -> dict[str, float]:
    """Estimate per-model 80% saturation rate.

    If Phase 1 baseline results are available, uses mean service time.
    Otherwise falls back to config default.
    """
    p3 = cfg["phase3"]
    default_rate = p3.get("arrival_rate_rps", 1.0)
    rates = {}

    for model_cfg in cfg["models"]:
        name = model_cfg["name"]
        if baseline_results_by_model and name in baseline_results_by_model:
            mean_service_s = baseline_results_by_model[name] / 1000.0
            if mean_service_s > 0:
                # 80% of theoretical max throughput (1/service_time)
                max_rps = 1.0 / mean_service_s
                target = max_rps * 0.8
                rates[name] = round(target, 2)
                log.info(
                    "  P3: %s — service=%.0fms, max=%.2f rps, target=%.2f rps (80%%)",
                    name,
                    mean_service_s * 1000,
                    max_rps,
                    target,
                )
                continue
        rates[name] = default_rate
        log.info("  P3: %s — using default rate %.2f rps", name, default_rate)

    return rates


def run_phase3(
    cfg: dict,
    run_dir: Path,
    writer: csv.DictWriter,
    baseline_service_ms: dict[str, float] | None = None,
) -> int:
    """Execute Phase 3: thermal stability test.

    Args:
        cfg: Experiment config.
        run_dir: Output directory.
        writer: CSV writer.
        baseline_service_ms: Dict of model_name -> mean wall_ms from Phase 1.
            Used to compute 80% saturation rate.  If None, uses config default.

    Returns number of rows written.
    """
    p3 = cfg["phase3"]
    models = cfg["models"]
    url = cfg["ollama_url"]
    max_tokens = cfg["max_new_tokens"]
    timeout = cfg.get("ollama_timeout_s", 120)
    duration_s = p3["duration_s"]
    seed = cfg.get("seed", 42)
    rows_written = 0

    target_rates = _estimate_saturation_rate(cfg, baseline_service_ms)

    gpu_mon = GpuMonitor(interval=cfg.get("gpu_poll_interval_s", 1.0))
    gpu_mon.start()

    try:
        for model_cfg in models:
            tag = model_cfg["ollama_tag"]
            model_name = model_cfg["name"]
            rate = target_rates.get(model_name, 1.0)

            # Generate enough prompts to cover the full duration
            n_expected = int(duration_s * rate) + 10
            rng = np.random.default_rng(seed)
            lengths = generate_prompt_lengths(
                n_expected,
                "uniform",
                p3["prompt_tokens_low"],
                p3["prompt_tokens_high"],
                rng=rng,
            )
            prompts = [generate_ollama_prompt(l) for l in lengths]

            log.info(
                "  P3: %s — %.2f rps for %ds (periodic arrivals)",
                model_name,
                rate,
                duration_s,
            )

            arrival_gen = timed_periodic_arrivals(duration_s, rate)

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
            log.info(
                "  P3: %s — %d/%d ok over %ds",
                model_name,
                n_ok,
                len(results),
                duration_s,
            )

            for r in results:
                row = {
                    "phase": "p3_thermal",
                    "model": model_name,
                    "num_parallel": 1,
                    "arrival_pattern": "periodic",
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
            GpuMonitor.save_csv(gpu_samples, run_dir / "gpu_phase3.csv")
            summary = GpuMonitor.summarize(gpu_samples)
            throttle = summary.get("thermal_throttle", {})
            log.info(
                "  P3 GPU: temp %.0f-%.0f°C, throttle detected=%s (%d samples, %.1f%%)",
                summary.get("temp_c", {}).get("min", 0),
                summary.get("temp_c", {}).get("max", 0),
                throttle.get("detected", False),
                throttle.get("n_samples", 0),
                throttle.get("pct_of_run", 0),
            )

    log.info("  Phase 3 complete: %d rows", rows_written)
    return rows_written
