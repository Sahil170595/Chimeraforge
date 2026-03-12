"""TR135: Run multi-agent concurrency x safety experiment.

Usage:
    python research/tr135/run.py [-v] [--skip-prep] [--skip-eval] [--skip-judge]

Steps:
  1. Prepare benchmarks (copy TR134 tasks, generate MMLU control)
  2. For each (model, N_agents) in randomized order:
     run all prompts through N concurrent agents
  3. Run LLM judge post-hoc on safety samples
  4. Run analysis (safety vs N, latency vs N, safety-latency correlation)
  5. Generate report

Design notes:
  - Each agent processes all prompts (gives N responses per prompt at N-level)
  - Analysis aggregates per-prompt across agents before computing stats
  - N-level ordering is randomized per model to avoid thermal/cache confounds
  - Prompt ordering is shuffled per agent to avoid sequence effects
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

from research.tr135.shared.utils import TR135_MODELS, N_AGENT_LEVELS

logger = logging.getLogger("tr135.run")


def _load_prompts(task_dir: Path) -> list[dict]:
    """Load all prompts from task YAML files with metadata."""
    prompts = []
    for path in sorted(task_dir.glob("*.yaml")):
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        task_name = data.get("name", path.stem)
        task_type = data.get("type", "unknown")
        template = data.get("prompt_template", "{instruction}")
        for sample in data.get("samples", []):
            prompt_text = template
            for key, val in sample.items():
                prompt_text = prompt_text.replace("{{ " + key + " }}", str(val))
            prompts.append({
                "task_name": task_name,
                "task_type": task_type,
                "sample_id": sample.get("id", ""),
                "prompt": prompt_text,
                "reference": sample.get("reference", ""),
                "correct_answers": sample.get("correct_answers", []),
                "incorrect_answers": sample.get("incorrect_answers", []),
                "sample_meta": {
                    k: v for k, v in sample.items()
                    if k in ("category", "stereotyped_idx", "anti_stereotyped_idx",
                             "answer_choice_0", "answer_choice_1", "answer_choice_2",
                             "context", "question", "jailbreak_type", "instruction")
                },
            })
    return prompts


async def _agent_loop(
    agent_id: int,
    model_tag: str,
    prompts: list[dict],
    ollama_url: str,
    max_tokens: int,
    timeout_s: float,
    seed: int,
    in_flight: list[int],
    t0: float,
) -> list[dict]:
    """Single agent's closed loop: send -> wait -> next prompt.

    Prompts are shuffled per agent (with agent-specific seed) to avoid
    ordering effects while maintaining reproducibility.
    """
    # Shuffle prompts for this agent (reproducible per agent_id)
    agent_prompts = list(prompts)
    random.Random(seed + agent_id).shuffle(agent_prompts)

    results = []
    async with httpx.AsyncClient() as client:
        for i, p in enumerate(agent_prompts):
            depth = in_flight[0]
            in_flight[0] += 1
            submit_time = time.perf_counter() - t0

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

            t_req = time.perf_counter()
            try:
                resp = await client.post(
                    f"{ollama_url}/api/generate",
                    json=payload,
                    timeout=timeout_s,
                )
                wall_ms = (time.perf_counter() - t_req) * 1000
                resp.raise_for_status()
                data = resp.json()
                response_text = data.get("response", "")
                ns_to_ms = 1e-6
                eval_ms = data.get("eval_duration", 0) * ns_to_ms
                prompt_tokens = data.get("prompt_eval_count", 0)
                completion_tokens = data.get("eval_count", 0)
            except httpx.TimeoutException:
                wall_ms = (time.perf_counter() - t_req) * 1000
                status = "timeout"
            except Exception as exc:
                wall_ms = (time.perf_counter() - t_req) * 1000
                status = f"error: {exc}"
            finally:
                in_flight[0] -= 1

            record = {
                "agent_id": agent_id,
                "in_flight_at_submit": depth,
                "submit_time_s": round(submit_time, 4),
                "wall_ms": round(wall_ms, 2),
                "eval_ms": round(eval_ms, 2),
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "status": status,
                "task_name": p["task_name"],
                "task_type": p["task_type"],
                "sample_id": p["sample_id"],
                "prompt": p["prompt"],
                "candidate": response_text,
                "reference": p["reference"],
                "correct_answers": p["correct_answers"],
                "incorrect_answers": p["incorrect_answers"],
                "sample_meta": p["sample_meta"],
            }
            results.append(record)

            if (i + 1) % 50 == 0:
                logger.info(
                    "  Agent %d: %d/%d (wall=%.0fms, depth=%d)",
                    agent_id, i + 1, len(agent_prompts), wall_ms, depth,
                )

    return results


async def _run_n_agents(
    model_tag: str,
    n_agents: int,
    prompts: list[dict],
    ollama_url: str,
    max_tokens: int,
    timeout_s: float,
    seed: int,
) -> list[dict]:
    """Run N concurrent agents, each processing all prompts."""
    in_flight: list[int] = [0]
    t0 = time.perf_counter()

    tasks = [
        asyncio.create_task(
            _agent_loop(i, model_tag, prompts, ollama_url, max_tokens,
                        timeout_s, seed, in_flight, t0)
        )
        for i in range(n_agents)
    ]

    all_results: list[dict] = []
    for completed in await asyncio.gather(*tasks, return_exceptions=True):
        if isinstance(completed, Exception):
            logger.error("Agent task failed: %s", completed)
            continue
        all_results.extend(completed)

    elapsed = time.perf_counter() - t0
    n_ok = sum(1 for r in all_results if r["status"] == "ok")
    logger.info(
        "N=%d complete: %d/%d ok, %.1fs elapsed",
        n_agents, n_ok, len(all_results), elapsed,
    )
    return all_results


def _warmup(model_tag: str, ollama_url: str, n: int = 3) -> None:
    """Send warmup requests to load model into VRAM."""
    import urllib.request
    for i in range(n):
        payload = json.dumps({
            "model": model_tag,
            "prompt": "Hello, how are you?",
            "stream": False,
            "options": {"num_predict": 16, "temperature": 0.0},
        }).encode()
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


def main() -> int:
    parser = argparse.ArgumentParser(description="TR135 concurrency x safety")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--skip-prep", action="store_true")
    parser.add_argument("--skip-eval", action="store_true")
    parser.add_argument("--skip-judge", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    with open(_DIR / "config.yaml", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    ollama_url = config["ollama_url"]
    max_tokens = config["max_new_tokens"]
    timeout_s = config["timeout_s"]
    seed = config["seed"]
    n_levels = config["n_agent_levels"]

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
    if not args.skip_eval:
        print("\n=== Step 2: Running N-agent safety evaluation ===")
        task_dir = _DIR / "tasks"
        prompts = _load_prompts(task_dir)
        logger.info("Loaded %d prompts from %s", len(prompts), task_dir)

        run_ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        run_dir = _REPO / config["output_dir"] / run_ts
        run_dir.mkdir(parents=True, exist_ok=True)

        with open(run_dir / "config_snapshot.yaml", "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False)

        samples_path = run_dir / "samples.jsonl"
        all_records: list[dict] = []

        for model_entry in config["models"]:
            model_name = model_entry["name"]
            model_tag = model_entry["ollama_tag"]

            logger.info("=== Model: %s (%s) ===", model_name, model_tag)
            _warmup(model_tag, ollama_url, n=config.get("warmup_requests", 3))

            # Randomize N-level order to avoid thermal/cache confounds
            shuffled_n = list(n_levels)
            random.Random(seed).shuffle(shuffled_n)
            logger.info("N-level order (randomized): %s", shuffled_n)

            for n_agents in shuffled_n:
                logger.info("--- N=%d agents, model=%s ---", n_agents, model_name)
                t_combo = time.perf_counter()

                results = asyncio.run(
                    _run_n_agents(model_tag, n_agents, prompts, ollama_url,
                                  max_tokens, timeout_s, seed)
                )

                for rec in results:
                    rec["model"] = model_name
                    rec["model_name"] = model_name
                    rec["n_agents"] = n_agents
                    rec["backend"] = "ollama"
                    rec["seed"] = seed
                    rec["repetition"] = 0
                all_records.extend(results)

                elapsed = time.perf_counter() - t_combo
                logger.info(
                    "N=%d, %s: %d records, %.1fs",
                    n_agents, model_name, len(results), elapsed,
                )

        with open(samples_path, "w", encoding="utf-8") as f:
            for rec in all_records:
                f.write(json.dumps(rec, default=str) + "\n")
        logger.info("Wrote %d total records to %s", len(all_records), samples_path)

    # Step 3: LLM judge
    if not args.skip_judge:
        print("\n=== Step 3: Running LLM judge ===")
        judge_cmd = [sys.executable, str(_DIR / "judge_analysis.py")]
        if args.verbose:
            judge_cmd.append("-v")
        result = subprocess.run(judge_cmd, cwd=_REPO)
        if result.returncode != 0:
            print("WARNING: Judge analysis failed (non-fatal)")

    # Step 4: Analyze
    print("\n=== Step 4: Running analysis ===")
    analyze_cmd = [sys.executable, str(_DIR / "analyze.py")]
    if args.verbose:
        analyze_cmd.append("-v")
    result = subprocess.run(analyze_cmd, cwd=_REPO)
    if result.returncode != 0:
        print("ERROR: Analysis failed")
        return result.returncode

    # Step 5: Generate report
    print("\n=== Step 5: Generating report ===")
    report_cmd = [sys.executable, str(_DIR / "generate_report.py")]
    if args.verbose:
        report_cmd.append("-v")
    result = subprocess.run(report_cmd, cwd=_REPO)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
