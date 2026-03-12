"""TR130 Phase 1 — Environment Validation.

3 backends × 3 models × 3 requests = ~27 rows.
Confirms: GPU access in Docker, model loading, API format, timing extraction.
Returns a skip-list of (backend, model) combos that failed validation.
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

log = logging.getLogger("tr130.phase1")


def run_phase1(
    cfg: dict,
    run_dir: Path,
    writer: csv.DictWriter,
) -> tuple[int, list[tuple[str, str]]]:
    """Execute Phase 1: environment validation.

    Returns (rows_written, skip_list) where skip_list is a list of
    (backend_name, model_name) tuples that failed validation and should
    be skipped in subsequent phases.
    """
    p1 = cfg["phase1"]
    models = cfg["models"]
    backends_cfg = cfg["backends"]
    max_tokens = cfg["max_new_tokens"]
    seed = cfg.get("seed", 42)
    n_per = p1["requests_per_combo"]
    rows_written = 0
    skip_list: list[tuple[str, str]] = []

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

                log.info(
                    "  P1: %s × %s — %d validation requests",
                    backend_name,
                    model_name,
                    n_per,
                )

                try:
                    backend.start(hf_id, model_ollama_tag=ollama_tag)
                    warmup = backend.warmup(n=1, max_tokens=8)
                    log.info("  P1: warmup %s", warmup)
                except Exception as exc:
                    log.error(
                        "  P1: SKIP %s × %s — start failed: %s",
                        backend_name,
                        model_name,
                        exc,
                    )
                    skip_list.append((backend_name, model_name))
                    with contextlib.suppress(Exception):
                        backend.stop()
                    continue

                rng = np.random.default_rng(seed)
                prompts = generate_prompts(
                    n_per,
                    rng=rng,
                    low=p1["prompt_tokens_low"],
                    high=p1["prompt_tokens_high"],
                )

                combo_failed = False
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
                        "  P1: %s × %s — %d/%d ok",
                        backend_name,
                        model_name,
                        n_ok,
                        len(results),
                    )

                    # If zero requests succeeded, mark for skip
                    if n_ok == 0:
                        combo_failed = True
                        log.warning(
                            "  P1: %s × %s — 0 ok, adding to skip list",
                            backend_name,
                            model_name,
                        )

                    rows_written += write_rows(
                        writer,
                        results,
                        "p1_validation",
                        backend_name,
                        model_name,
                        1,
                    )
                except Exception as exc:
                    log.error(
                        "  P1: %s × %s — execution failed: %s",
                        backend_name,
                        model_name,
                        exc,
                    )
                    combo_failed = True
                finally:
                    backend.stop()

                if combo_failed:
                    skip_list.append((backend_name, model_name))
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

    if skip_list:
        log.warning("  Phase 1 skip list: %s", skip_list)
    log.info("  Phase 1 complete: %d rows", rows_written)
    return rows_written, skip_list
