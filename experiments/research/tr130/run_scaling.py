"""TR130 Phase 3 — N-Agent Scaling (CORE).

3 backends × 3 models × N={1,2,4,8} × 30 req/agent.
36 configs, ~4,050 rows.
Computes Amdahl serial fractions per backend.
Cross-backend statistical comparison.
"""

from __future__ import annotations

import asyncio
import contextlib
import csv
import logging
from pathlib import Path
import time

import numpy as np

from research.tr130.shared.agent_executor import run_n_agent_test
from research.tr130.shared.backends import ServingBackend, create_backend
from research.tr130.shared.gpu_monitor import GpuMonitor
from research.tr130.shared.utils import generate_prompts, write_rows

log = logging.getLogger("tr130.phase3")


def run_phase3(
    cfg: dict,
    run_dir: Path,
    writer: csv.DictWriter,
    skip_list: list[tuple[str, str]] | None = None,
) -> int:
    """Execute Phase 3: N-agent scaling sweep.

    Returns number of rows written.
    skip_list: (backend, model) pairs from Phase 1 to skip.
    """
    p3 = cfg["phase3"]
    models = cfg["models"]
    backends_cfg = cfg["backends"]
    max_tokens = cfg["max_new_tokens"]
    seed = cfg.get("seed", 42)
    req_per_agent = p3["requests_per_agent"]
    n_levels = p3["n_agent_levels"]
    cooldown_s = p3.get("cooldown_between_configs_s", 5)
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
                        "  P3: SKIP %s × %s (failed Phase 1 validation)",
                        backend_name,
                        model_name,
                    )
                    continue

                log.info(
                    "  P3: %s × %s — N-levels %s, %d req/agent",
                    backend_name,
                    model_name,
                    n_levels,
                    req_per_agent,
                )

                try:
                    backend.start(hf_id, model_ollama_tag=ollama_tag)
                    backend.warmup(n=cfg.get("warmup_requests", 3))
                except Exception as exc:
                    log.error(
                        "  P3: SKIP %s × %s — start failed: %s",
                        backend_name,
                        model_name,
                        exc,
                    )
                    with contextlib.suppress(Exception):
                        backend.stop()
                    continue

                try:
                    for level_idx, n_agents in enumerate(n_levels):
                        total_requests = n_agents * req_per_agent
                        log.info(
                            "  P3: %s × %s — N=%d agents, %d req/agent (%d total)",
                            backend_name,
                            model_name,
                            n_agents,
                            req_per_agent,
                            total_requests,
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
                                backend=backend,
                                n_agents=n_agents,
                                requests_per_agent=req_per_agent,
                                prompts=prompts,
                                max_tokens=max_tokens,
                            )
                        )

                        n_ok = sum(1 for r in results if r.status == "ok")
                        log.info(
                            "  P3: %s × %s N=%d — %d/%d ok",
                            backend_name,
                            model_name,
                            n_agents,
                            n_ok,
                            len(results),
                        )

                        rows_written += write_rows(
                            writer,
                            results,
                            "p3_scaling",
                            backend_name,
                            model_name,
                            n_agents,
                        )

                        # Cooldown between N-level configs
                        if level_idx < len(n_levels) - 1 and cooldown_s > 0:
                            log.info(
                                "  P3: cooldown %ds before next config",
                                cooldown_s,
                            )
                            time.sleep(cooldown_s)
                except Exception as exc:
                    log.error(
                        "  P3: %s × %s — execution failed: %s",
                        backend_name,
                        model_name,
                        exc,
                    )
                finally:
                    backend.stop()

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
