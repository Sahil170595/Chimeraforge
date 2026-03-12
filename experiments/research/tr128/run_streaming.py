"""TR128 Phase 4 — Streaming Performance.

Compares batch vs stream response modes under load, measures TTFT and
inter-CHUNK latency (ichunk) via Ollama NDJSON streaming.

IMPORTANT: Inter-chunk != inter-token due to TCP buffering.  Ollama may
batch multiple tokens per network read.  TTFT *is* reliable (first
non-empty chunk always marks the first generated token).

3 models x 3 rates x 2 modes x 30 req = 540 rows.
"""

from __future__ import annotations

import asyncio
import csv
import json
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

log = logging.getLogger("tr128.phase4")


def run_phase4(
    cfg: dict,
    run_dir: Path,
    writer: csv.DictWriter,
    ichunk_file: Path | None = None,
) -> int:
    """Execute Phase 4: streaming performance comparison.

    Args:
        cfg: Experiment configuration.
        run_dir: Output directory for this run.
        writer: CSV writer for metrics.
        ichunk_file: Path to write raw inter-chunk latency arrays as JSONL.

    Returns number of rows written.
    """
    p4 = cfg["phase4"]
    models = cfg["models"]
    url = cfg["ollama_url"]
    max_tokens = cfg["max_new_tokens"]
    timeout = cfg.get("ollama_timeout_s", 120)
    n_per = p4["requests_per_combo"]
    seed = cfg.get("seed", 42)
    rows_written = 0

    ichunk_fh = None
    if ichunk_file:
        ichunk_fh = open(ichunk_file, "w", encoding="utf-8")

    gpu_mon = GpuMonitor(interval=cfg.get("gpu_poll_interval_s", 1.0))
    gpu_mon.start()

    try:
        for model_cfg in models:
            tag = model_cfg["ollama_tag"]
            model_name = model_cfg["name"]

            for rate in p4["arrival_rates"]:
                for mode in p4["response_modes"]:
                    log.info(
                        "  P4: %s / rate=%.1f / %s",
                        model_name,
                        rate,
                        mode,
                    )
                    rng = np.random.default_rng(seed)

                    lengths = generate_prompt_lengths(
                        n_per,
                        "uniform",
                        p4["prompt_tokens_low"],
                        p4["prompt_tokens_high"],
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
                            executor=mode,
                            max_tokens=max_tokens,
                            timeout=timeout,
                        )
                    )

                    for r in results:
                        ichunk = r.ichunk_values_ms
                        ichunk_arr = np.array(ichunk) if ichunk else np.array([])

                        row = {
                            "phase": "p4_stream",
                            "model": model_name,
                            "num_parallel": 1,
                            "arrival_pattern": "poisson",
                            "arrival_rate_rps": rate,
                            "prompt_distribution": "uniform",
                            "response_mode": mode,
                            "request_id": r.request_id,
                            "queue_depth_at_submit": r.queue_depth_at_submit,
                            "wall_ms": round(r.wall_ms, 2),
                            "ttft_ms": (
                                round(r.ttft_ms, 2) if r.ttft_ms is not None else ""
                            ),
                            "ichunk_mean_ms": (
                                round(float(ichunk_arr.mean()), 2)
                                if len(ichunk_arr) > 0
                                else ""
                            ),
                            "ichunk_p95_ms": (
                                round(float(np.percentile(ichunk_arr, 95)), 2)
                                if len(ichunk_arr) > 0
                                else ""
                            ),
                            "ichunk_jitter_cv": (
                                round(float(ichunk_arr.std() / ichunk_arr.mean()), 4)
                                if len(ichunk_arr) > 1 and ichunk_arr.mean() > 0
                                else ""
                            ),
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

                        # Write raw inter-chunk latency to JSONL
                        if ichunk_fh and ichunk:
                            record = {
                                "model": model_name,
                                "rate": rate,
                                "mode": mode,
                                "request_id": r.request_id,
                                "ichunk_ms": [round(v, 2) for v in ichunk],
                            }
                            ichunk_fh.write(json.dumps(record) + "\n")

    finally:
        if ichunk_fh:
            ichunk_fh.close()
        gpu_samples = gpu_mon.stop()
        if gpu_samples:
            GpuMonitor.save_csv(gpu_samples, run_dir / "gpu_phase4.csv")

    log.info("  Phase 4 complete: %d rows", rows_written)
    return rows_written
