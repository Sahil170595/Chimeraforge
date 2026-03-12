"""Patch BBQ samples in an existing Phase 3 run with the fixed multi-category task file.

Steps:
  1. Strip old BBQ entries from samples.jsonl
  2. Re-run BBQ eval for all 26 model-quant combos (via Ollama directly)
  3. Append new BBQ entries to samples.jsonl
  4. Strip old BBQ entries from phase3_judged.jsonl
  5. Re-run judge on new BBQ entries
  6. Append to phase3_judged.jsonl
  7. Re-run analyze + report
"""

from __future__ import annotations

import json
import logging
import sys
import time
import urllib.request
from pathlib import Path

import yaml

_DIR = Path(__file__).resolve().parent
_REPO = _DIR.parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from research.tr134.shared.llm_judge import LLMJudge
from research.tr134.shared.utils import find_latest_run

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("tr134.phase3.patch_bbq")

OLLAMA_URL = "http://localhost:11434"


def _generate(model_tag: str, prompt: str, max_tokens: int = 256) -> tuple[str, float]:
    """Call Ollama generate and return (response, elapsed_ms)."""
    payload = json.dumps({
        "model": model_tag,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.0, "num_predict": max_tokens},
    }).encode()
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=300) as resp:
        data = json.loads(resp.read())
    elapsed = (time.perf_counter() - t0) * 1000
    return data.get("response", ""), elapsed


def main() -> int:
    # Find latest run
    results_dir = _REPO / "research" / "tr134" / "results" / "phase3"
    run_dir = find_latest_run(results_dir)
    if not run_dir:
        logger.error("No run directory found in %s", results_dir)
        return 1
    logger.info("Patching run: %s", run_dir)

    # Load config for model list
    config_path = _DIR / "config.yaml"
    with open(config_path) as f:
        config = yaml.safe_load(f)
    models = config["models"]

    # Load BBQ task file
    bbq_path = _DIR / "tasks" / "bbq_bias.yaml"
    with open(bbq_path) as f:
        bbq_task = yaml.safe_load(f)
    bbq_samples = bbq_task["samples"]
    prompt_template = bbq_task["prompt_template"]
    logger.info("BBQ: %d samples, %d models = %d evals",
                len(bbq_samples), len(models), len(bbq_samples) * len(models))

    # Step 1: Strip old BBQ from samples.jsonl
    samples_path = run_dir / "samples.jsonl"
    kept = []
    removed = 0
    with open(samples_path) as f:
        for line in f:
            rec = json.loads(line)
            if rec.get("task_name") == "bbq_bias":
                removed += 1
            else:
                kept.append(line)
    logger.info("Stripped %d old BBQ entries from samples.jsonl (%d kept)", removed, len(kept))

    # Step 2: Run BBQ eval for all models
    new_bbq = []
    total = len(models) * len(bbq_samples)
    count = 0
    for model_entry in models:
        tag = model_entry["ollama_tag"]
        model_name = model_entry["name"]
        for sample in bbq_samples:
            count += 1
            # Render prompt
            prompt = prompt_template
            for key in ("context", "question", "answer_choice_0", "answer_choice_1", "answer_choice_2"):
                prompt = prompt.replace("{{ " + key + " }}", sample.get(key, ""))

            try:
                response, elapsed = _generate(tag, prompt)
            except Exception as e:
                logger.warning("[%d/%d] %s/%s FAILED: %s", count, total, model_name, sample["id"], e)
                response, elapsed = "", 0.0

            record = {
                "model": model_name,
                "model_name": model_name,
                "backend": "ollama",
                "task_name": "bbq_bias",
                "task_type": "safety_bias",
                "sample_id": sample["id"],
                "prompt": prompt,
                "candidate": response,
                "reference": sample.get("reference", ""),
                "latency_ms": elapsed,
                "generation_time_ms": elapsed,
                "repetition": 0,
                "seed": 42,
                "metrics": {},
                "backend_metadata": {"model_tag": tag},
            }
            new_bbq.append(json.dumps(record) + "\n")

            if count % 100 == 0:
                rate = count / max(1, (time.perf_counter() - t0_eval))
                eta = (total - count) / max(0.01, rate)
                logger.info("[%d/%d] %s/%s (%.1f/s, ETA %.0fm)",
                            count, total, model_name, sample["id"], rate, eta / 60)

    # Step 3: Write patched samples.jsonl
    with open(samples_path, "w") as f:
        f.writelines(kept)
        f.writelines(new_bbq)
    logger.info("Wrote %d new BBQ + %d existing = %d total samples",
                len(new_bbq), len(kept), len(kept) + len(new_bbq))

    # Step 4: Strip old BBQ from phase3_judged.jsonl
    judged_path = run_dir / "phase3_judged.jsonl"
    kept_judged = []
    if judged_path.exists():
        with open(judged_path) as f:
            for line in f:
                rec = json.loads(line)
                if rec.get("task_name") != "bbq_bias":
                    kept_judged.append(line)
        logger.info("Stripped BBQ from judged (%d kept)", len(kept_judged))

    # Step 5: Judge new BBQ entries
    judge = LLMJudge()
    if not judge.health_check():
        logger.warning("Judge model not available, skipping judge for BBQ")
    else:
        logger.info("Judging %d new BBQ entries...", len(new_bbq))
        new_judged = []
        for i, line in enumerate(new_bbq):
            rec = json.loads(line)
            # Extract BBQ fields from the prompt for the judge
            result = judge.judge_bias(
                context="",
                question=rec["prompt"],
                response=rec["candidate"],
                choice_a="", choice_b="", choice_c="",
            )
            judged_rec = {
                "model_name": rec["model_name"],
                "task_name": "bbq_bias",
                "sample_id": rec["sample_id"],
                "judge_label": result.label,
                "judge_raw_response": result.raw_response,
                "judge_model": result.judge_model,
                "parse_success": result.parse_success,
                "judge_elapsed_ms": result.elapsed_ms,
            }
            new_judged.append(json.dumps(judged_rec) + "\n")
            if (i + 1) % 200 == 0:
                logger.info("Judged %d/%d BBQ entries", i + 1, len(new_bbq))

        kept_judged.extend(new_judged)
        logger.info("Total judged: %d", len(kept_judged))

    with open(judged_path, "w") as f:
        f.writelines(kept_judged)

    # Step 6: Re-run analyze
    logger.info("Re-running analysis...")
    import subprocess
    result = subprocess.run(
        [sys.executable, str(_DIR / "analyze.py"), "-v"],
        cwd=_REPO,
    )
    if result.returncode != 0:
        logger.error("Analysis failed")
        return result.returncode

    # Step 7: Re-run report
    logger.info("Re-generating report...")
    result = subprocess.run(
        [sys.executable, str(_DIR / "generate_report.py"), "-v"],
        cwd=_REPO,
    )
    return result.returncode


t0_eval = time.perf_counter()
if __name__ == "__main__":
    sys.exit(main())
