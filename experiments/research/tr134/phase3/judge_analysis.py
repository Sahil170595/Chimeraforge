"""TR134 Phase 3: Standalone LLM judge runner (post-hoc).

Reads stored candidates from samples.jsonl and runs LLM-as-judge classification
on all safety-related samples. Writes phase3_judged.jsonl for downstream analysis.

Does NOT go through the eval framework (respects architecture rule — this is
TR-specific post-hoc processing).

Usage:
    python research/tr134/phase3/judge_analysis.py [-v] [--run-dir PATH] [--limit N]
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import sys
import time

_DIR = Path(__file__).resolve().parent
_REPO = _DIR.parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from research.tr134.shared.llm_judge import LLMJudge
from research.tr134.shared.utils import (
    ALL_SAFETY_TASKS,
    extract_base_model,
    extract_quant_level,
    find_latest_run,
)
from scripts.eval.analysis.aggregator import load_sample_jsonl

logger = logging.getLogger("tr134.phase3.judge_analysis")


def _load_task_yamls(task_dir: Path) -> dict[str, dict]:
    """Load task YAML files for metadata access."""
    import yaml

    yamls = {}
    if not task_dir.exists():
        return yamls
    for path in task_dir.glob("*.yaml"):
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if data and "name" in data:
            yamls[data["name"]] = data
    return yamls


def _build_sample_index(task_yamls: dict[str, dict]) -> dict[str, dict[str, dict]]:
    """Build {task_name -> {sample_id -> sample_data}} index."""
    index: dict[str, dict[str, dict]] = {}
    for task_name, yaml_data in task_yamls.items():
        sample_map: dict[str, dict] = {}
        for sample in yaml_data.get("samples", []):
            sid = sample.get("id", "")
            if sid:
                sample_map[sid] = sample
        index[task_name] = sample_map
    return index


def run_judge(run_dir: Path, limit: int = 0) -> int:
    """Run LLM judge on all safety samples in run_dir."""
    jsonl_path = run_dir / "samples.jsonl"
    if not jsonl_path.exists():
        logger.error("No samples.jsonl found in %s", run_dir)
        return 1

    # Health check
    judge = LLMJudge()
    health = judge.health_check()
    if not health["reachable"]:
        logger.error("Cannot reach Ollama: %s", health.get("error", "unknown"))
        return 1
    if not health["model_available"]:
        logger.error(
            "Judge model %s not available. Pull it first: ollama pull %s",
            judge.model, judge.model,
        )
        return 1
    logger.info("Judge model %s is available", judge.model)

    # Load records
    records = load_sample_jsonl(jsonl_path)
    safety_records = [r for r in records if r.task_name in ALL_SAFETY_TASKS]
    logger.info("Total records: %d, safety records: %d", len(records), len(safety_records))

    if limit > 0:
        safety_records = safety_records[:limit]
        logger.info("Limited to %d records", limit)

    # Load task YAMLs for metadata
    task_yamls = _load_task_yamls(_DIR / "tasks")
    sample_index = _build_sample_index(task_yamls)

    # Run judge on each safety record
    output_path = run_dir / "phase3_judged.jsonl"
    judged_count = 0
    parse_failures = 0
    t_start = time.perf_counter()

    with open(output_path, "w", encoding="utf-8") as f:
        for i, rec in enumerate(safety_records):
            if (i + 1) % 100 == 0:
                elapsed = time.perf_counter() - t_start
                rate = (i + 1) / elapsed
                eta = (len(safety_records) - i - 1) / rate if rate > 0 else 0
                logger.info(
                    "Progress: %d/%d (%.1f/s, ETA %.0fm)",
                    i + 1, len(safety_records), rate, eta / 60,
                )

            sample_data = sample_index.get(rec.task_name, {}).get(rec.sample_id, {})
            entry = {
                "sample_id": rec.sample_id,
                "task_name": rec.task_name,
                "model": rec.model,
                "base_model": extract_base_model(rec.model),
                "quant": extract_quant_level(rec.model),
            }

            try:
                if rec.task_name in ("advbench_refusal", "jailbreak_amplification"):
                    prompt = sample_data.get("instruction", rec.sample_id)
                    result = judge.judge_refusal(prompt, rec.candidate)
                elif rec.task_name == "truthfulqa":
                    question = sample_data.get("question", rec.sample_id)
                    correct = sample_data.get("correct_answers", [])
                    incorrect = sample_data.get("incorrect_answers", [])
                    result = judge.judge_truthfulness(
                        question, rec.candidate, correct, incorrect
                    )
                elif rec.task_name == "bbq_bias":
                    context = sample_data.get("context", "")
                    question = sample_data.get("question", "")
                    choice_a = sample_data.get("answer_choice_0", "")
                    choice_b = sample_data.get("answer_choice_1", "")
                    choice_c = sample_data.get("answer_choice_2", "")
                    result = judge.judge_bias(
                        context, question, rec.candidate,
                        choice_a, choice_b, choice_c,
                    )
                else:
                    continue

                entry["judge_label"] = result.label
                entry["judge_raw_response"] = result.raw_response
                entry["judge_model"] = result.judge_model
                entry["judge_parse_success"] = result.parse_success
                entry["judge_elapsed_ms"] = round(result.elapsed_ms, 1)

                if not result.parse_success:
                    parse_failures += 1

            except Exception as e:
                logger.warning("Judge failed for %s/%s: %s", rec.model, rec.sample_id, e)
                entry["judge_label"] = "ERROR"
                entry["judge_raw_response"] = str(e)
                entry["judge_model"] = judge.model
                entry["judge_parse_success"] = False
                entry["judge_elapsed_ms"] = 0.0
                parse_failures += 1

            f.write(json.dumps(entry, default=str) + "\n")
            judged_count += 1

    elapsed_total = time.perf_counter() - t_start
    logger.info(
        "Judge analysis complete: %d judged, %d parse failures, %.1fm elapsed",
        judged_count, parse_failures, elapsed_total / 60,
    )
    logger.info("Output: %s", output_path)

    # Summary
    print(f"\n{'='*60}")
    print("Phase 3 LLM Judge Analysis Complete")
    print(f"  Judged: {judged_count} samples")
    print(f"  Parse failures: {parse_failures}")
    print(f"  Elapsed: {elapsed_total / 60:.1f} minutes")
    print(f"  Output: {output_path}")
    print(f"{'='*60}")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="TR134 Phase 3 LLM judge analysis")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--run-dir", type=str, default=None)
    parser.add_argument("--limit", type=int, default=0, help="Limit number of samples to judge")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if args.run_dir:
        run_dir = Path(args.run_dir)
    else:
        run_dir = find_latest_run("research/tr134/results/phase3")

    if not run_dir or not run_dir.exists():
        logger.error("No run directory found. Run evaluation first.")
        return 1

    return run_judge(run_dir, limit=args.limit)


if __name__ == "__main__":
    sys.exit(main())
