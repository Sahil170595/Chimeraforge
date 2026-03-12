"""TR130 Phase 2 — Single-Agent Baseline.

3 backends × 3 models × 50 requests = ~450 rows.
Establishes per-backend reference throughput for efficiency calculations.
"""

from __future__ import annotations

import asyncio
import contextlib
import csv
import logging
from pathlib import Path

import numpy as np

from research.tr130.shared.agent_executor import run_n_agent_test
from research.tr130.shared.backends import ServingBackend, create_backend
from research.tr130.shared.gpu_monitor import GpuMonitor
from research.tr130.shared.utils import generate_prompts, write_rows

log = logging.getLogger("tr130.phase2")


def run_phase2(
    cfg: dict,
    run_dir: Path,
    writer: csv.DictWriter,
    skip_list: list[tuple[str, str]] | None = None,
) -> int:
    """Execute Phase 2: single-agent baseline.

    Returns number of rows written.
    skip_list: (backend, model) pairs from Phase 1 to skip.
    """
    p2 = cfg["phase2"]
    models = cfg["models"]
    backends_cfg = cfg["backends"]
    max_tokens = cfg["max_new_tokens"]
    seed = cfg.get("seed", 42)
    n_per = p2["requests_per_model"]
    rows_written = 0
    skip_set = set(skip_list) if skip_list else set()

    gpu_mon = GpuMonitor(interval=cfg.get("gpu_poll_interval_s", 1.0))
    gpu_mon.start()

    try:
        for backend_name in cfg.get("backend_order", list(backends_cfg.keys())):
            bcfg = backends_cfg[backend_name]
            backend: ServingBackend = create_backend(backend_name, bcfg)

            for model_cfg in models:
                model_name = model_cfg["name"]
                hf_id = model_cfg["hf_id"]
                ollama_tag = model_cfg.get("ollama_tag")

                if (backend_name, model_name) in skip_set:
                    log.warning(
                        "  P2: SKIP %s × %s (failed Phase 1 validation)",
                        backend_name,
                        model_name,
                    )
                    continue

                log.info(
                    "  P2: %s × %s — %d serial requests (N=1)",
                    backend_name,
                    model_name,
                    n_per,
                )

                try:
                    backend.start(hf_id, model_ollama_tag=ollama_tag)
                    backend.warmup(n=cfg.get("warmup_requests", 3))
                except Exception as exc:
                    log.error(
                        "  P2: SKIP %s × %s — start failed: %s",
                        backend_name,
                        model_name,
                        exc,
                    )
                    with contextlib.suppress(Exception):
                        backend.stop()
                    continue

                rng = np.random.default_rng(seed)
                prompts = generate_prompts(
                    n_per,
                    rng=rng,
                    low=p2["prompt_tokens_low"],
                    high=p2["prompt_tokens_high"],
                )

                try:
                    results = asyncio.run(
                        run_n_agent_test(
                            backend=backend,
                            n_agents=1,
                            requests_per_agent=n_per,
                            prompts=prompts,
                            max_tokens=max_tokens,
                        )
                    )

                    n_ok = sum(1 for r in results if r.status == "ok")
                    log.info(
                        "  P2: %s × %s — %d/%d ok",
                        backend_name,
                        model_name,
                        n_ok,
                        len(results),
                    )

                    rows_written += write_rows(
                        writer,
                        results,
                        "p2_baseline",
                        backend_name,
                        model_name,
                        1,
                    )
                except Exception as exc:
                    log.error(
                        "  P2: %s × %s — execution failed: %s",
                        backend_name,
                        model_name,
                        exc,
                    )
                finally:
                    backend.stop()
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
