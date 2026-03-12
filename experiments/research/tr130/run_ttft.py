"""TR130 Phase 4 — TTFT Streaming Comparison.

3 backends × 3 models × 30 streaming requests = ~270 rows.
Time-To-First-Token comparison across serving stacks.
Uses generate_stream() for TTFT measurement.
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

log = logging.getLogger("tr130.phase4")


def run_phase4(
    cfg: dict,
    run_dir: Path,
    writer: csv.DictWriter,
    skip_list: list[tuple[str, str]] | None = None,
) -> int:
    """Execute Phase 4: TTFT streaming comparison.

    Returns number of rows written.
    skip_list: (backend, model) pairs from Phase 1 to skip.
    """
    p4 = cfg["phase4"]
    models = cfg["models"]
    backends_cfg = cfg["backends"]
    max_tokens = cfg["max_new_tokens"]
    seed = cfg.get("seed", 42)
    n_per = p4["requests_per_model"]
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
                        "  P4: SKIP %s × %s (failed Phase 1 validation)",
                        backend_name,
                        model_name,
                    )
                    continue

                log.info(
                    "  P4: %s × %s — %d streaming requests (TTFT)",
                    backend_name,
                    model_name,
                    n_per,
                )

                try:
                    backend.start(hf_id, model_ollama_tag=ollama_tag)
                    backend.warmup(n=cfg.get("warmup_requests", 3))
                except Exception as exc:
                    log.error(
                        "  P4: SKIP %s × %s — start failed: %s",
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
                    low=p4["prompt_tokens_low"],
                    high=p4["prompt_tokens_high"],
                )

                try:
                    results = asyncio.run(
                        run_n_agent_test(
                            backend=backend,
                            n_agents=1,
                            requests_per_agent=n_per,
                            prompts=prompts,
                            max_tokens=max_tokens,
                            stream=True,
                        )
                    )

                    n_ok = sum(1 for r in results if r.status == "ok")
                    has_ttft = sum(
                        1 for r in results if r.ttft_ms is not None and r.ttft_ms > 0
                    )
                    log.info(
                        "  P4: %s × %s — %d/%d ok, %d with TTFT",
                        backend_name,
                        model_name,
                        n_ok,
                        len(results),
                        has_ttft,
                    )

                    rows_written += write_rows(
                        writer,
                        results,
                        "p4_ttft",
                        backend_name,
                        model_name,
                        1,
                    )
                except Exception as exc:
                    log.error(
                        "  P4: %s × %s — execution failed: %s",
                        backend_name,
                        model_name,
                        exc,
                    )
                finally:
                    backend.stop()
    finally:
        gpu_samples = gpu_mon.stop()
        if gpu_samples:
            GpuMonitor.save_csv(gpu_samples, run_dir / "gpu_phase4.csv")
            summary = GpuMonitor.summarize(gpu_samples)
            log.info(
                "  P4 GPU: %.0f°C mean, %.0f%% util mean",
                summary.get("temp_c", {}).get("mean", 0),
                summary.get("gpu_util_pct", {}).get("mean", 0),
            )

    log.info("  Phase 4 complete: %d rows", rows_written)
    return rows_written
