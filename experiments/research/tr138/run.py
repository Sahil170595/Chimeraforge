"""TR138: Run batch inference safety under non-determinism experiment.

Usage:
    python research/tr138/run.py [-v] [--skip-prep] [--skip-eval] [--skip-judge]
      [--phases 1,2,3,4]

Steps:
  1. Prepare benchmarks (copy TR134 safety + capability tasks)
  2. For each selected phase (if not --skip-eval):
     Phase 1: Batch size x output determinism on vLLM (3 models x 6 batch sizes)
     Phase 2: Co-batching interference on vLLM (3 models x 4 conditions)
     Phase 3: Quantization x concurrency on Ollama (3 models x 3 quants x 3 concurrency)
     Phase 4: True batching validation on vLLM prompt lists (2 models x 3 batch sizes)
  3. Run LLM judge post-hoc (non-fatal)
  4. Run analysis
  5. Generate report

Design notes:
  - Phase 1 sends prompts in synchronized batches of exactly batch_size.
    All requests in a batch are dispatched concurrently and we wait for
    all to complete before starting the next batch.  This forces the
    vLLM scheduler to process exactly N requests simultaneously, unlike
    continuous batching where request timing is uncontrolled. Tail groups
    are padded with discarded fillers so analyzed prompts always see the
    stated dispatch size.
  - Phase 2 tests co-batching interference with a true solo control plus
    benign, adversarial, and contextual-safety filler pools. The target
    position is counterbalanced within the request group and recorded.
    Only the target prompt's response is recorded.
  - Phase 3 uses Ollama with concurrent requests (not true batching) to
    measure the interaction between quantization level and concurrent load.
  - Phase 4 uses a single vLLM completions call with a prompt list to
    validate whether the Phase 1 safety effect survives explicit tensor batching.
  - All phases write to a shared samples.jsonl in the run directory.
  - vLLM lifecycle managed via create_backend (TR130 backend abstraction).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import random
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
import yaml

_DIR = Path(__file__).resolve().parent
_REPO = _DIR.parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from research.tr130.shared.backends import create_backend
from research.tr130.shared.docker_utils import docker_available, docker_gpu_available
from research.tr138.shared.utils import (
    TR138_VLLM_MODELS,
    TR138_OLLAMA_MODELS,
    PHASE1_BATCH_SIZES,
    PHASE2_BATCH_SIZE,
    PHASE2_CONDITIONS,
    PHASE2_ADVERSARIAL_TASKS,
    PHASE2_CONTEXTUAL_TASKS,
    PHASE2_SAFETY_TASKS,
    PHASE3_CONCURRENCY,
    PHASE3_QUANTS,
    PHASE3_SAFETY_TASKS,
    PHASE4_BATCH_SIZES,
    PHASE4_TASK_LIMITS,
    BENIGN_PROMPTS,
    CAPABILITY_TASKS,
    get_ollama_quant_tag,
)

logger = logging.getLogger("tr138.run")


# ── Prompt loading ──────────────────────────────────────────────────


def _load_prompts(
    task_dir: Path, task_filter: set[str] | None = None
) -> list[dict]:
    """Load prompts from task YAML files with metadata.

    Parameters
    ----------
    task_dir : Directory containing task YAML files.
    task_filter : If provided, only load tasks whose name is in this set.
        When None, all tasks are loaded.
    """
    prompts = []
    for path in sorted(task_dir.glob("*.yaml")):
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        task_name = data.get("name", path.stem)
        if task_filter is not None and task_name not in task_filter:
            continue
        task_type = data.get("type", "unknown")
        template = data.get("prompt_template", "{instruction}")
        for sample in data.get("samples", []):
            prompt_text = template
            for key, val in sample.items():
                prompt_text = prompt_text.replace(
                    "{{ " + key + " }}", str(val)
                )
            prompts.append(
                {
                    "task_name": task_name,
                    "task_type": task_type,
                    "sample_id": sample.get("id", ""),
                    "prompt": prompt_text,
                    "reference": sample.get("reference", ""),
                    "correct_answers": sample.get("correct_answers", []),
                    "incorrect_answers": sample.get("incorrect_answers", []),
                    "sample_meta": {
                        k: v
                        for k, v in sample.items()
                        if k
                        in (
                            "category",
                            "stereotyped_idx",
                            "anti_stereotyped_idx",
                            "answer_choice_0",
                            "answer_choice_1",
                            "answer_choice_2",
                            "context",
                            "question",
                            "jailbreak_type",
                            "instruction",
                        )
                    },
                }
            )
    return prompts


def _subset_prompts_by_task(
    prompts: list[dict],
    task_limits: dict[str, int],
) -> list[dict]:
    """Take a deterministic per-task subset while preserving source order."""
    kept: list[dict] = []
    seen: dict[str, int] = {}
    for prompt in prompts:
        task = prompt.get("task_name", "")
        limit = task_limits.get(task)
        if limit is None:
            continue
        count = seen.get(task, 0)
        if count >= limit:
            continue
        kept.append(prompt)
        seen[task] = count + 1
    return kept


# ── Phase 1: Batch Size x Output Determinism (vLLM) ────────────────


async def _run_synchronized_batch(
    prompts: list[dict],
    batch_size: int,
    api_url: str,
    model_name: str,
    max_tokens: int,
    seed: int,
) -> list[dict]:
    """Send prompts in synchronized batches of exactly batch_size.

    Unlike continuous batching (where requests flow freely), this ensures
    exactly batch_size requests are in-flight simultaneously.  Each batch
    is dispatched concurrently via asyncio, and we wait for ALL requests
    in the batch to complete before sending the next batch.
    """
    records = []
    async with httpx.AsyncClient(timeout=180.0) as client:
        for batch_start in range(0, len(prompts), batch_size):
            batch = prompts[batch_start : batch_start + batch_size]
            dispatch_items: list[tuple[dict, bool]] = [
                (p, True) for p in batch
            ]

            # Pad the tail so every analyzed prompt experiences the
            # requested dispatch size, while discarding filler outputs.
            while len(dispatch_items) < batch_size:
                filler_idx = (batch_start + len(dispatch_items)) % len(prompts)
                dispatch_items.append((prompts[filler_idx], False))

            async def _single_request(p: dict, record_output: bool) -> dict | None:
                payload = {
                    "model": model_name,
                    "prompt": p["prompt"],
                    "max_tokens": max_tokens,
                    "temperature": 0.0,
                    "seed": seed,
                }
                t0 = time.perf_counter()
                try:
                    resp = await client.post(
                        f"{api_url}/v1/completions",
                        json=payload,
                    )
                    wall_ms = (time.perf_counter() - t0) * 1000
                    resp.raise_for_status()
                    data = resp.json()
                    response_text = data["choices"][0]["text"]
                    usage = data.get("usage", {})
                    prompt_tokens = usage.get("prompt_tokens", 0)
                    completion_tokens = usage.get("completion_tokens", 0)
                    status = "ok"
                except Exception as exc:
                    wall_ms = (time.perf_counter() - t0) * 1000
                    response_text = ""
                    status = f"error: {exc}"
                    prompt_tokens = 0
                    completion_tokens = 0

                if not record_output:
                    return None

                return {
                    "phase": 1,
                    "batch_size": batch_size,
                    "dispatch_batch_size": batch_size,
                    "tail_padded": len(batch) < batch_size,
                    "model": model_name,
                    "backend": "vllm",
                    "backend_label": "vllm_fp16",
                    "quant": "FP16",
                    "task_name": p["task_name"],
                    "task_type": p["task_type"],
                    "sample_id": p["sample_id"],
                    "prompt": p["prompt"],
                    "candidate": response_text,
                    "reference": str(p["reference"]) if p["reference"] else "",
                    "correct_answers": p.get("correct_answers", []),
                    "incorrect_answers": p.get("incorrect_answers", []),
                    "sample_meta": p.get("sample_meta", {}),
                    "wall_ms": round(wall_ms, 2),
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "status": status,
                    "seed": seed,
                    "repetition": 0,
                }

            tasks = [
                asyncio.create_task(_single_request(p, record_output))
                for p, record_output in dispatch_items
            ]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in batch_results:
                if isinstance(r, Exception):
                    logger.error("Batch request failed: %s", r)
                    continue
                if r is None:
                    continue
                records.append(r)

            if (batch_start // batch_size + 1) % 10 == 0:
                logger.info(
                    "  Phase 1 bs=%d: %d/%d batches",
                    batch_size,
                    batch_start // batch_size + 1,
                    (len(prompts) + batch_size - 1) // batch_size,
                )

    return records


def _run_phase1(
    config: dict,
    task_dir: Path,
    seed: int,
    max_tokens: int,
) -> list[dict]:
    """Phase 1: batch size sweep on vLLM."""
    logger.info("=== Phase 1: Batch Size x Output Determinism (vLLM) ===")

    prompts = _load_prompts(task_dir)
    logger.info("Phase 1: loaded %d prompts (all tasks)", len(prompts))

    batch_sizes = config["phase1"].get("batch_sizes", PHASE1_BATCH_SIZES)
    vllm_cfg = config["backends"]["vllm"]
    api_url = f"http://localhost:{vllm_cfg.get('port', 8000)}"
    all_records: list[dict] = []

    for model_entry in config["phase1"]["models"]:
        model_name = model_entry["name"]
        hf_id = model_entry["hf_id"]

        logger.info("--- Phase 1 model: %s (%s) ---", model_name, hf_id)

        # Start vLLM container
        backend = create_backend("vllm", vllm_cfg)
        try:
            backend.start(model_hf_id=hf_id)
        except Exception as e:
            logger.error("Failed to start vLLM for %s: %s", model_name, e)
            continue

        # Warmup
        try:
            warmup_info = backend.warmup(
                prompt="Hello",
                n=config.get("warmup_requests", 3),
                max_tokens=16,
            )
            logger.info("Warmup: %s", warmup_info)
        except Exception as e:
            logger.warning("Warmup failed: %s", e)

        # Run each batch size
        for bs in batch_sizes:
            logger.info(
                "  Phase 1: model=%s, batch_size=%d, prompts=%d",
                model_name,
                bs,
                len(prompts),
            )
            t0 = time.perf_counter()

            records = asyncio.run(
                _run_synchronized_batch(
                    prompts=prompts,
                    batch_size=bs,
                    api_url=api_url,
                    model_name=hf_id,
                    max_tokens=max_tokens,
                    seed=seed,
                )
            )

            # Patch model name (use short name, not hf_id)
            for rec in records:
                rec["model"] = model_name
                rec["model_name"] = model_name

            elapsed = time.perf_counter() - t0
            n_ok = sum(1 for r in records if r["status"] == "ok")
            logger.info(
                "  Phase 1 bs=%d, %s: %d/%d ok, %.1fs",
                bs,
                model_name,
                n_ok,
                len(records),
                elapsed,
            )
            all_records.extend(records)

        # Stop vLLM container
        try:
            backend.stop()
        except Exception as e:
            logger.warning("vLLM stop failed: %s", e)

        # Cooldown between models
        cooldown = config.get("cooldown_between_models_s", 10)
        if cooldown > 0:
            logger.info("Cooldown %ds...", cooldown)
            time.sleep(cooldown)

    logger.info("Phase 1 complete: %d total records", len(all_records))
    return all_records


# ── Phase 2: Co-Batching Interference (vLLM) ───────────────────────


async def _run_co_batch_condition(
    target_prompt: dict,
    filler_prompts: list[dict],
    condition: str,
    target_position: int,
    api_url: str,
    model_name: str,
    max_tokens: int,
    seed: int,
) -> dict:
    """Send 1 target plus zero or more fillers as a synchronized request group.

    Only the target prompt's response is recorded; fillers are discarded.
    The target position is explicitly controlled and recorded.
    """
    target_idx = target_position

    async with httpx.AsyncClient(timeout=180.0) as client:
        all_prompts = list(filler_prompts)
        insert_at = max(0, min(target_position, len(all_prompts)))
        all_prompts.insert(insert_at, target_prompt)

        async def _request(idx: int, p: dict) -> tuple[int, dict]:
            payload = {
                "model": model_name,
                "prompt": p["prompt"],
                "max_tokens": max_tokens,
                "temperature": 0.0,
                "seed": seed,
            }
            t0 = time.perf_counter()
            try:
                resp = await client.post(
                    f"{api_url}/v1/completions",
                    json=payload,
                )
                wall_ms = (time.perf_counter() - t0) * 1000
                resp.raise_for_status()
                data = resp.json()
                response_text = data["choices"][0]["text"]
                usage = data.get("usage", {})
                prompt_tokens = usage.get("prompt_tokens", 0)
                completion_tokens = usage.get("completion_tokens", 0)
                status = "ok"
            except Exception as exc:
                wall_ms = (time.perf_counter() - t0) * 1000
                response_text = ""
                status = f"error: {exc}"
                prompt_tokens = 0
                completion_tokens = 0

            return idx, {
                "response_text": response_text,
                "wall_ms": wall_ms,
                "status": status,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
            }

        tasks = [
            asyncio.create_task(_request(i, p))
            for i, p in enumerate(all_prompts)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    # Find the target result
    target_result = None
    for r in results:
        if isinstance(r, Exception):
            logger.error("Co-batch request failed: %s", r)
            continue
        idx, data = r
        if idx == target_idx:
            target_result = data
            break

    if target_result is None:
        target_result = {
            "response_text": "",
            "wall_ms": 0.0,
            "status": "error: target not found",
            "prompt_tokens": 0,
            "completion_tokens": 0,
        }

    return {
        "phase": 2,
        "batch_size": len(all_prompts),
        "condition": condition,
        "co_batch_condition": condition,
        "co_batch_filler_type": condition,
        "filler_count": len(filler_prompts),
        "target_position": target_idx,
        "model": model_name,
        "backend": "vllm",
        "backend_label": "vllm_fp16",
        "quant": "FP16",
        "task_name": target_prompt["task_name"],
        "task_type": target_prompt["task_type"],
        "sample_id": target_prompt["sample_id"],
        "prompt": target_prompt["prompt"],
        "candidate": target_result["response_text"],
        "reference": (
            str(target_prompt["reference"]) if target_prompt["reference"] else ""
        ),
        "correct_answers": target_prompt.get("correct_answers", []),
        "incorrect_answers": target_prompt.get("incorrect_answers", []),
        "sample_meta": target_prompt.get("sample_meta", {}),
        "wall_ms": round(target_result["wall_ms"], 2),
        "prompt_tokens": target_result["prompt_tokens"],
        "completion_tokens": target_result["completion_tokens"],
        "status": target_result["status"],
        "seed": seed,
        "repetition": 0,
    }


def _run_phase2(
    config: dict,
    task_dir: Path,
    seed: int,
    max_tokens: int,
) -> list[dict]:
    """Phase 2: co-batching interference on vLLM."""
    logger.info("=== Phase 2: Co-Batching Interference (vLLM) ===")

    # Load safety prompts only
    safety_prompts = _load_prompts(task_dir, task_filter=PHASE2_SAFETY_TASKS)
    capability_prompts = _load_prompts(task_dir, task_filter=CAPABILITY_TASKS)
    logger.info("Phase 2: loaded %d safety prompts", len(safety_prompts))
    logger.info("Phase 2: loaded %d capability prompts for benign fillers", len(capability_prompts))

    # Build filler pools
    rng = random.Random(seed)
    batch_size = config["phase2"].get("batch_size", PHASE2_BATCH_SIZE)
    n_fillers = batch_size - 1

    # Adversarial fillers are genuinely harmful/jailbreak prompts.
    adversarial_pool = [
        p for p in safety_prompts if p["task_name"] in PHASE2_ADVERSARIAL_TASKS
    ]

    # Safety fillers are non-adversarial safety-evaluation prompts.
    safety_pool = [
        p for p in safety_prompts if p["task_name"] in PHASE2_CONTEXTUAL_TASKS
    ]

    # Benign fillers primarily come from capability tasks; hand-written prompts
    # remain as fallback to avoid a small repeated toy pool.
    benign_pool = list(capability_prompts)
    benign_pool.extend(
        {
            "task_name": "benign_filler",
            "task_type": "benign",
            "sample_id": f"benign_{i}",
            "prompt": p,
            "reference": "",
            "correct_answers": [],
            "incorrect_answers": [],
            "sample_meta": {},
        }
        for i, p in enumerate(BENIGN_PROMPTS)
    )

    vllm_cfg = config["backends"]["vllm"]
    api_url = f"http://localhost:{vllm_cfg.get('port', 8000)}"
    conditions = config["phase2"].get("conditions", PHASE2_CONDITIONS)
    all_records: list[dict] = []

    for model_entry in config["phase2"]["models"]:
        model_name = model_entry["name"]
        hf_id = model_entry["hf_id"]

        logger.info("--- Phase 2 model: %s (%s) ---", model_name, hf_id)

        # Start vLLM
        backend = create_backend("vllm", vllm_cfg)
        try:
            backend.start(model_hf_id=hf_id)
        except Exception as e:
            logger.error("Failed to start vLLM for %s: %s", model_name, e)
            continue

        # Warmup
        try:
            warmup_info = backend.warmup(
                prompt="Hello",
                n=config.get("warmup_requests", 3),
                max_tokens=16,
            )
            logger.info("Warmup: %s", warmup_info)
        except Exception as e:
            logger.warning("Warmup failed: %s", e)

        # For each safety prompt, run each condition
        for i, target in enumerate(safety_prompts):
            position_order = list(range(batch_size))
            rng.shuffle(position_order)
            target_positions = {
                condition: position_order[idx]
                for idx, condition in enumerate(conditions)
            }
            for condition in conditions:
                # Select fillers based on condition.
                if condition == "solo":
                    fillers = []
                elif condition == "benign":
                    fillers = rng.sample(
                        benign_pool, min(n_fillers, len(benign_pool))
                    )
                    # Pad if pool is smaller than n_fillers
                    while len(fillers) < n_fillers:
                        fillers.append(rng.choice(benign_pool))
                elif condition == "adversarial":
                    # Draw harmful/jailbreak fillers, excluding the target if needed.
                    candidates = [
                        p
                        for p in adversarial_pool
                        if not (
                            p["task_name"] == target["task_name"]
                            and p["sample_id"] == target["sample_id"]
                        )
                    ]
                    fillers = rng.sample(
                        candidates, min(n_fillers, len(candidates))
                    )
                    while len(fillers) < n_fillers and candidates:
                        fillers.append(rng.choice(candidates))
                elif condition == "safety":
                    # Draw contextual/non-adversarial safety prompts.
                    candidates = [
                        p
                        for p in safety_pool
                        if not (
                            p["task_name"] == target["task_name"]
                            and p["sample_id"] == target["sample_id"]
                        )
                    ]
                    fillers = rng.sample(
                        candidates, min(n_fillers, len(candidates))
                    )
                    while len(fillers) < n_fillers and candidates:
                        fillers.append(rng.choice(candidates))
                else:
                    logger.warning("Unknown condition: %s", condition)
                    continue

                record = asyncio.run(
                    _run_co_batch_condition(
                        target_prompt=target,
                        filler_prompts=fillers,
                        condition=condition,
                        target_position=target_positions[condition] if condition != "solo" else 0,
                        api_url=api_url,
                        model_name=hf_id,
                        max_tokens=max_tokens,
                        seed=seed,
                    )
                )

                # Patch model name
                record["model"] = model_name
                record["model_name"] = model_name
                all_records.append(record)

            if (i + 1) % 50 == 0:
                logger.info(
                    "  Phase 2: %s %d/%d targets (%d records)",
                    model_name,
                    i + 1,
                    len(safety_prompts),
                    len(all_records),
                )

        # Stop vLLM
        try:
            backend.stop()
        except Exception as e:
            logger.warning("vLLM stop failed: %s", e)

        # Cooldown between models
        cooldown = config.get("cooldown_between_models_s", 10)
        if cooldown > 0:
            logger.info("Cooldown %ds...", cooldown)
            time.sleep(cooldown)

    logger.info("Phase 2 complete: %d total records", len(all_records))
    return all_records


# ── Phase 3: Quantization x Concurrency (Ollama) ───────────────────


async def _run_concurrent_ollama(
    prompts: list[dict],
    concurrency: int,
    ollama_url: str,
    model_tag: str,
    model_name: str,
    quant: str,
    max_tokens: int,
    timeout_s: float,
    seed: int,
) -> list[dict]:
    """Send prompts with N concurrent requests through Ollama.

    Uses a semaphore to limit concurrency.  Unlike Phase 1's synchronized
    batches, this is a continuous-flow pattern where the next request
    starts as soon as a slot opens.
    """
    sem = asyncio.Semaphore(concurrency)
    records: list[dict] = []
    lock = asyncio.Lock()
    t_global = time.perf_counter()

    async with httpx.AsyncClient(timeout=timeout_s) as client:
        async def _single(p: dict) -> None:
            async with sem:
                submit_time = time.perf_counter() - t_global
                payload = {
                    "model": model_tag,
                    "prompt": p["prompt"],
                    "stream": False,
                    "options": {
                        "num_predict": max_tokens,
                        "temperature": 0.0,
                        "seed": seed,
                    },
                }

                wall_ms = 0.0
                response_text = ""
                status = "ok"
                eval_ms = 0.0
                prompt_tokens = 0
                completion_tokens = 0

                t0 = time.perf_counter()
                try:
                    resp = await client.post(
                        f"{ollama_url}/api/generate",
                        json=payload,
                    )
                    wall_ms = (time.perf_counter() - t0) * 1000
                    resp.raise_for_status()
                    data = resp.json()
                    response_text = data.get("response", "")
                    ns_to_ms = 1e-6
                    eval_ms = data.get("eval_duration", 0) * ns_to_ms
                    prompt_tokens = data.get("prompt_eval_count", 0)
                    completion_tokens = data.get("eval_count", 0)
                except httpx.TimeoutException:
                    wall_ms = (time.perf_counter() - t0) * 1000
                    status = "timeout"
                except Exception as exc:
                    wall_ms = (time.perf_counter() - t0) * 1000
                    status = f"error: {exc}"

                record = {
                    "phase": 3,
                    "concurrency": concurrency,
                    "quant": quant,
                    "model": model_name,
                    "model_name": model_name,
                    "backend": "ollama",
                    "backend_label": f"ollama_{quant.lower()}",
                    "task_name": p["task_name"],
                    "task_type": p["task_type"],
                    "sample_id": p["sample_id"],
                    "prompt": p["prompt"],
                    "candidate": response_text,
                    "reference": str(p["reference"]) if p["reference"] else "",
                    "correct_answers": p.get("correct_answers", []),
                    "incorrect_answers": p.get("incorrect_answers", []),
                    "sample_meta": p.get("sample_meta", {}),
                    "wall_ms": round(wall_ms, 2),
                    "eval_ms": round(eval_ms, 2),
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "status": status,
                    "seed": seed,
                    "repetition": 0,
                    "submit_time_s": round(submit_time, 4),
                }

                async with lock:
                    records.append(record)

        tasks = [asyncio.create_task(_single(p)) for p in prompts]
        await asyncio.gather(*tasks, return_exceptions=True)

    return records


def _warmup_ollama(model_tag: str, ollama_url: str, n: int = 3) -> None:
    """Send warmup requests to load model into VRAM."""
    import urllib.request

    for i in range(n):
        payload = json.dumps(
            {
                "model": model_tag,
                "prompt": "Hello, how are you?",
                "stream": False,
                "options": {"num_predict": 16, "temperature": 0.0},
            }
        ).encode()
        req = urllib.request.Request(
            f"{ollama_url}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                resp.read()
            logger.debug("Warmup %d/%d ok", i + 1, n)
        except Exception as e:
            logger.warning("Warmup %d/%d failed: %s", i + 1, n, e)


def _run_phase3(
    config: dict,
    task_dir: Path,
    seed: int,
    max_tokens: int,
) -> list[dict]:
    """Phase 3: quantization x concurrency on Ollama."""
    logger.info("=== Phase 3: Quantization x Concurrency (Ollama) ===")

    # Load safety subset (advbench + jailbreak)
    prompts = _load_prompts(task_dir, task_filter=PHASE3_SAFETY_TASKS)
    logger.info("Phase 3: loaded %d safety-subset prompts", len(prompts))

    ollama_cfg = config["backends"]["ollama"]
    ollama_url = f"http://localhost:{ollama_cfg.get('port', 11434)}"
    timeout_s = ollama_cfg.get("timeout_s", 300)
    quant_levels = config["phase3"].get("quant_levels", PHASE3_QUANTS)
    concurrency_levels = config["phase3"].get(
        "concurrency_levels", PHASE3_CONCURRENCY
    )
    cooldown = config.get("cooldown_between_models_s", 10)
    all_records: list[dict] = []

    for model_entry in config["phase3"]["models"]:
        model_name = model_entry["name"]
        base_tag = model_entry["ollama_tag"]

        for quant in quant_levels:
            model_tag = get_ollama_quant_tag(base_tag, quant)
            logger.info(
                "--- Phase 3: %s @ %s (tag=%s) ---",
                model_name,
                quant,
                model_tag,
            )

            # Pull/load model at quant level via Ollama backend
            backend = create_backend("ollama", ollama_cfg)
            try:
                backend.start(
                    model_hf_id=model_entry.get("hf_id", ""),
                    model_ollama_tag=model_tag,
                )
            except Exception as e:
                logger.error(
                    "Failed to start Ollama for %s @ %s: %s",
                    model_name,
                    quant,
                    e,
                )
                continue

            # Warmup
            _warmup_ollama(
                model_tag,
                ollama_url,
                n=config.get("warmup_requests", 3),
            )

            for conc in concurrency_levels:
                logger.info(
                    "  Phase 3: %s @ %s, concurrency=%d, prompts=%d",
                    model_name,
                    quant,
                    conc,
                    len(prompts),
                )
                t0 = time.perf_counter()

                records = asyncio.run(
                    _run_concurrent_ollama(
                        prompts=prompts,
                        concurrency=conc,
                        ollama_url=ollama_url,
                        model_tag=model_tag,
                        model_name=model_name,
                        quant=quant,
                        max_tokens=max_tokens,
                        timeout_s=timeout_s,
                        seed=seed,
                    )
                )

                elapsed = time.perf_counter() - t0
                n_ok = sum(1 for r in records if r["status"] == "ok")
                logger.info(
                    "  Phase 3 conc=%d, %s @ %s: %d/%d ok, %.1fs",
                    conc,
                    model_name,
                    quant,
                    n_ok,
                    len(records),
                    elapsed,
                )
                all_records.extend(records)

            # Unload model to free VRAM before next quant level
            try:
                backend.stop()
            except Exception as e:
                logger.warning("Ollama stop failed: %s", e)

            # Cooldown between quant levels
            if cooldown > 0:
                logger.info("Cooldown %ds...", cooldown)
                time.sleep(cooldown)

    logger.info("Phase 3 complete: %d total records", len(all_records))
    return all_records


# -- Phase 4: True batching validation on vLLM prompt lists -----------------


async def _run_true_batch_vllm(
    prompts: list[dict],
    batch_size: int,
    api_url: str,
    model_name: str,
    max_tokens: int,
    seed: int,
) -> list[dict]:
    """Run explicit prompt-list batching through one completions call per group."""
    records: list[dict] = []
    async with httpx.AsyncClient(timeout=180.0) as client:
        for batch_start in range(0, len(prompts), batch_size):
            batch = prompts[batch_start : batch_start + batch_size]
            dispatch_items: list[tuple[dict, bool]] = [
                (p, True) for p in batch
            ]
            while len(dispatch_items) < batch_size:
                filler_idx = (batch_start + len(dispatch_items)) % len(prompts)
                dispatch_items.append((prompts[filler_idx], False))

            payload = {
                "model": model_name,
                "prompt": [p["prompt"] for p, _ in dispatch_items],
                "max_tokens": max_tokens,
                "temperature": 0.0,
                "seed": seed,
            }
            t0 = time.perf_counter()
            try:
                resp = await client.post(f"{api_url}/v1/completions", json=payload)
                wall_ms = (time.perf_counter() - t0) * 1000
                resp.raise_for_status()
                data = resp.json()
                usage = data.get("usage", {})
                prompt_tokens = usage.get("prompt_tokens", 0)
                completion_tokens = usage.get("completion_tokens", 0)
                choices = data.get("choices", [])
                choice_map: dict[int, dict] = {}
                for idx, choice in enumerate(choices):
                    raw_idx = choice.get("index", idx)
                    try:
                        mapped_idx = int(raw_idx)
                    except Exception:
                        mapped_idx = idx
                    choice_map[mapped_idx] = choice
                status = "ok"
            except Exception as exc:
                wall_ms = (time.perf_counter() - t0) * 1000
                prompt_tokens = 0
                completion_tokens = 0
                choice_map = {}
                status = f"error: {exc}"

            analyzed_in_batch = sum(1 for _, keep in dispatch_items if keep)
            for idx, (prompt_rec, keep) in enumerate(dispatch_items):
                if not keep:
                    continue
                choice = choice_map.get(idx, {})
                response_text = choice.get("text", "") if status == "ok" else ""
                rec_status = status if status != "ok" or response_text else (
                    "ok" if status == "ok" else status
                )
                records.append(
                    {
                        "phase": 4,
                        "batch_size": batch_size,
                        "dispatch_batch_size": batch_size,
                        "tail_padded": len(batch) < batch_size,
                        "batch_mode": "true_prompt_list",
                        "true_batching": True,
                        "analyzed_in_batch": analyzed_in_batch,
                        "model": model_name,
                        "backend": "vllm",
                        "backend_label": "vllm_fp16_true_batch",
                        "quant": "FP16",
                        "task_name": prompt_rec["task_name"],
                        "task_type": prompt_rec["task_type"],
                        "sample_id": prompt_rec["sample_id"],
                        "prompt": prompt_rec["prompt"],
                        "candidate": response_text,
                        "reference": (
                            str(prompt_rec["reference"])
                            if prompt_rec["reference"]
                            else ""
                        ),
                        "correct_answers": prompt_rec.get("correct_answers", []),
                        "incorrect_answers": prompt_rec.get("incorrect_answers", []),
                        "sample_meta": prompt_rec.get("sample_meta", {}),
                        "wall_ms": round(wall_ms, 2),
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "status": rec_status,
                        "seed": seed,
                        "repetition": 0,
                    }
                )

            if (batch_start // batch_size + 1) % 10 == 0:
                logger.info(
                    "  Phase 4 bs=%d: %d/%d batches",
                    batch_size,
                    batch_start // batch_size + 1,
                    (len(prompts) + batch_size - 1) // batch_size,
                )

    return records


def _run_phase4(
    config: dict,
    task_dir: Path,
    seed: int,
    max_tokens: int,
) -> list[dict]:
    """Phase 4: explicit prompt-list batching on vLLM."""
    logger.info("=== Phase 4: True Batching Validation (vLLM prompt lists) ===")

    all_prompts = _load_prompts(task_dir)
    task_limits = config["phase4"].get("task_limits", PHASE4_TASK_LIMITS)
    prompts = _subset_prompts_by_task(all_prompts, task_limits)
    logger.info("Phase 4: loaded %d reduced prompts", len(prompts))

    batch_sizes = config["phase4"].get("batch_sizes", PHASE4_BATCH_SIZES)
    vllm_cfg = config["backends"]["vllm"]
    api_url = f"http://localhost:{vllm_cfg.get('port', 8000)}"
    all_records: list[dict] = []

    for model_entry in config["phase4"]["models"]:
        model_name = model_entry["name"]
        hf_id = model_entry["hf_id"]

        logger.info("--- Phase 4 model: %s (%s) ---", model_name, hf_id)

        backend = create_backend("vllm", vllm_cfg)
        try:
            backend.start(model_hf_id=hf_id)
        except Exception as e:
            logger.error("Failed to start vLLM for %s: %s", model_name, e)
            continue

        try:
            warmup_info = backend.warmup(
                prompt="Hello",
                n=config.get("warmup_requests", 3),
                max_tokens=16,
            )
            logger.info("Warmup: %s", warmup_info)
        except Exception as e:
            logger.warning("Warmup failed: %s", e)

        for bs in batch_sizes:
            logger.info(
                "  Phase 4: model=%s, batch_size=%d, prompts=%d",
                model_name,
                bs,
                len(prompts),
            )
            t0 = time.perf_counter()
            records = asyncio.run(
                _run_true_batch_vllm(
                    prompts=prompts,
                    batch_size=bs,
                    api_url=api_url,
                    model_name=hf_id,
                    max_tokens=max_tokens,
                    seed=seed,
                )
            )
            for rec in records:
                rec["model"] = model_name
                rec["model_name"] = model_name
            elapsed = time.perf_counter() - t0
            n_ok = sum(1 for r in records if r["status"] == "ok")
            logger.info(
                "  Phase 4 bs=%d, %s: %d/%d ok, %.1fs",
                bs,
                model_name,
                n_ok,
                len(records),
                elapsed,
            )
            all_records.extend(records)

        try:
            backend.stop()
        except Exception as e:
            logger.warning("vLLM stop failed: %s", e)

        cooldown = config.get("cooldown_between_models_s", 10)
        if cooldown > 0:
            logger.info("Cooldown %ds...", cooldown)
            time.sleep(cooldown)

    logger.info("Phase 4 complete: %d total records", len(all_records))
    return all_records


# ── Main ────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description="TR138 batch inference safety under non-determinism"
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--skip-prep", action="store_true")
    parser.add_argument("--skip-eval", action="store_true")
    parser.add_argument("--skip-judge", action="store_true")
    parser.add_argument(
        "--phases",
        type=str,
        default="1,2,3,4",
        help="Comma-separated phases to run (default: 1,2,3,4)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    with open(_DIR / "config.yaml", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    max_tokens = config["max_new_tokens"]
    seed = config["seed"]
    selected_phases = {int(p.strip()) for p in args.phases.split(",")}

    # Pre-flight: check Docker if vLLM phases selected
    needs_docker = selected_phases & {1, 2, 4}
    if needs_docker and not args.skip_eval:
        if not docker_available():
            print(
                "ERROR: Docker is required for vLLM backends (Phase 1/2/4) "
                "but is not available."
            )
            print(
                "       Start Docker Desktop or install Docker Engine, then retry."
            )
            return 1
        if not docker_gpu_available():
            print(
                "WARNING: Docker GPU access not detected. vLLM may fail."
            )
            print(
                "         Ensure nvidia-container-toolkit is installed."
            )

    # Step 1: Prepare benchmarks
    if not args.skip_prep:
        print("=== Step 1: Preparing benchmarks ===")
        prep_cmd = [sys.executable, str(_DIR / "prepare_benchmarks.py")]
        if args.verbose:
            prep_cmd.append("-v")
        result = subprocess.run(prep_cmd, cwd=_REPO)
        if result.returncode != 0:
            print("ERROR: Benchmark preparation failed")
            return result.returncode

    # Step 2: Run evaluation
    run_dir = None
    if not args.skip_eval:
        print("\n=== Step 2: Running batch inference safety evaluation ===")
        task_dir = _DIR / "tasks"

        run_ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        run_dir = _REPO / config["output_dir"] / run_ts
        run_dir.mkdir(parents=True, exist_ok=True)

        with open(run_dir / "config_snapshot.yaml", "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False)

        all_records: list[dict] = []
        samples_path = run_dir / "samples.jsonl"

        def _save_incremental() -> None:
            """Save all records accumulated so far."""
            with open(samples_path, "w", encoding="utf-8") as fout:
                for rec in all_records:
                    fout.write(json.dumps(rec, default=str) + "\n")
            logger.info(
                "Incremental save: %d records to %s",
                len(all_records), samples_path,
            )

        # Phase 1: Batch size sweep on vLLM
        if 1 in selected_phases:
            phase1_records = _run_phase1(config, task_dir, seed, max_tokens)
            all_records.extend(phase1_records)
            _save_incremental()

        # Phase 2: Co-batch interference on vLLM
        if 2 in selected_phases:
            phase2_records = _run_phase2(config, task_dir, seed, max_tokens)
            all_records.extend(phase2_records)
            _save_incremental()

        # Phase 3: Quant x concurrency on Ollama
        if 3 in selected_phases:
            phase3_records = _run_phase3(config, task_dir, seed, max_tokens)
            all_records.extend(phase3_records)
            _save_incremental()

        # Phase 4: True batching validation on vLLM prompt lists
        if 4 in selected_phases:
            phase4_records = _run_phase4(config, task_dir, seed, max_tokens)
            all_records.extend(phase4_records)
            _save_incremental()

        logger.info(
            "Final: %d total records in %s", len(all_records), samples_path
        )

    # Resolve run_dir for downstream steps
    if run_dir is not None:
        run_dir_arg = ["--run-dir", str(run_dir)]
    else:
        run_dir_arg = []  # let downstream steps use find_latest_run

    # Step 3: LLM judge
    if not args.skip_judge:
        print("\n=== Step 3: Running LLM judge ===")
        judge_cmd = [sys.executable, str(_DIR / "judge_analysis.py")]
        if args.verbose:
            judge_cmd.append("-v")
        judge_cmd.extend(run_dir_arg)
        result = subprocess.run(judge_cmd, cwd=_REPO)
        if result.returncode != 0:
            print("WARNING: Judge analysis failed (non-fatal)")

    # Step 4: Analyze
    print("\n=== Step 4: Running analysis ===")
    analyze_cmd = [sys.executable, str(_DIR / "analyze.py")]
    if args.verbose:
        analyze_cmd.append("-v")
    analyze_cmd.extend(run_dir_arg)
    result = subprocess.run(analyze_cmd, cwd=_REPO)
    if result.returncode != 0:
        print("ERROR: Analysis failed")
        return result.returncode

    # Step 5: Generate report
    print("\n=== Step 5: Generating report ===")
    report_cmd = [sys.executable, str(_DIR / "generate_report.py")]
    if args.verbose:
        report_cmd.append("-v")
    report_cmd.extend(run_dir_arg)
    result = subprocess.run(report_cmd, cwd=_REPO)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
