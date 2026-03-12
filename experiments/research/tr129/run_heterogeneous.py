"""TR129 Phase 4 — Heterogeneous Multi-Model Agents.

N=4 agents with mixed model assignments, OLLAMA_MAX_LOADED_MODELS=3.
4 configs: homo_1b, mixed_small (1b+1.5b), mixed_size (1b+3b), all_different.
4 configs × 4 agents × 30 req/agent.

Tests model switching overhead and multi-model scheduling.
~480 rows, ~15 min.
"""

from __future__ import annotations

import asyncio
import csv
import logging
from pathlib import Path

import numpy as np

from research.tr129.shared.agent_executor import (
    AgentConfig,
    run_heterogeneous_test,
)
from research.tr129.shared.gpu_monitor import GpuMonitor
from research.tr129.shared.utils import generate_prompts

log = logging.getLogger("tr129.phase4")


def run_phase4(
    cfg: dict,
    run_dir: Path,
    writer: csv.DictWriter,
) -> int:
    """Execute Phase 4: heterogeneous multi-model agents.

    Returns number of rows written.
    """
    p4 = cfg["phase4"]
    url = cfg["ollama_url"]
    max_tokens = cfg["max_new_tokens"]
    timeout = cfg.get("ollama_timeout_s", 120)
    req_per_agent = p4["requests_per_agent"]
    n_agents = p4["n_agents"]
    seed = cfg.get("seed", 42)
    rows_written = 0

    gpu_mon = GpuMonitor(interval=cfg.get("gpu_poll_interval_s", 1.0))
    gpu_mon.start()

    try:
        for config_entry in p4["configs"]:
            config_id = config_entry["id"]
            model_tags = config_entry["agents"]
            total_requests = len(model_tags) * req_per_agent

            log.info(
                "  P4: config=%s — %d agents, models=%s, %d req/agent",
                config_id,
                len(model_tags),
                model_tags,
                req_per_agent,
            )

            rng = np.random.default_rng(seed)
            prompts = generate_prompts(
                max(total_requests, 50),
                rng=rng,
                low=p4["prompt_tokens_low"],
                high=p4["prompt_tokens_high"],
            )

            agents = []
            for i, model_tag in enumerate(model_tags):
                start = (i * req_per_agent) % len(prompts)
                agent_prompts = []
                for j in range(req_per_agent):
                    idx = (start + j) % len(prompts)
                    agent_prompts.append(prompts[idx])

                agents.append(
                    AgentConfig(
                        agent_id=i,
                        model=model_tag,
                        n_requests=req_per_agent,
                        prompts=agent_prompts,
                        think_time_ms=0.0,
                    )
                )

            results = asyncio.run(
                run_heterogeneous_test(
                    agents=agents,
                    url=url,
                    max_tokens=max_tokens,
                    timeout=timeout,
                )
            )

            n_ok = sum(1 for r in results if r.status == "ok")
            log.info(
                "  P4: config=%s — %d/%d ok",
                config_id,
                n_ok,
                len(results),
            )

            # Map agent_id → model name for CSV
            tag_to_name = {}
            for m in cfg["models"]:
                tag_to_name[m["ollama_tag"]] = m["name"]

            for r in results:
                # Find model name from agent's tag
                agent_tag = model_tags[r.agent_id]
                model_name = tag_to_name.get(agent_tag, agent_tag)

                row = {
                    "phase": "p4_heterogeneous",
                    "model": model_name,
                    "agent_id": r.agent_id,
                    "n_agents": n_agents,
                    "think_time_ms": 0,
                    "config_id": config_id,
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
            GpuMonitor.save_csv(gpu_samples, run_dir / "gpu_phase4.csv")
            summary = GpuMonitor.summarize(gpu_samples)
            log.info(
                "  P4 GPU: %.0f°C mean, %.0f%% util mean",
                summary.get("temp_c", {}).get("mean", 0),
                summary.get("gpu_util_pct", {}).get("mean", 0),
            )

    log.info("  Phase 4 complete: %d rows", rows_written)
    return rows_written
