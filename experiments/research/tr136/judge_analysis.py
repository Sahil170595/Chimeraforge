"""TR136: LLM judge post-hoc analysis for cross-backend safety samples.

Reads samples.jsonl, runs LLM-as-judge on safety tasks, writes tr136_judged.jsonl.

Usage:
    python research/tr136/judge_analysis.py [-v] [--run-dir PATH] [--limit N]
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import sys
import time

_DIR = Path(__file__).resolve().parent
_REPO = _DIR.parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from research.tr134.shared.llm_judge import LLMJudge
from research.tr136.shared.utils import SAFETY_TASKS, find_latest_run

logger = logging.getLogger("tr136.judge_analysis")


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
    """Run LLM judge on safety samples."""
    jsonl_path = run_dir / "samples.jsonl"
    if not jsonl_path.exists():
        logger.error("No samples.jsonl in %s", run_dir)
        return 1

    judge = LLMJudge()
    health = judge.health_check()
    if not health["reachable"]:
        logger.error("Cannot reach Ollama: %s", health.get("error", "unknown"))
        return 1
    if not health["model_available"]:
        logger.error("Judge model %s not available", judge.model)
        return 1
    logger.info("Judge model %s ready", judge.model)

    records = []
    with open(jsonl_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    safety_records = [r for r in records if r.get("task_name") in SAFETY_TASKS]
    logger.info("Total: %d, safety: %d", len(records), len(safety_records))

    if limit > 0:
        safety_records = safety_records[:limit]

    task_yamls = _load_task_yamls(_DIR / "tasks")
    sample_index = _build_sample_index(task_yamls)

    output_path = run_dir / "tr136_judged.jsonl"
    judged = 0
    parse_failures = 0
    t_start = time.perf_counter()

    with open(output_path, "w", encoding="utf-8") as f:
        for i, rec in enumerate(safety_records):
            if (i + 1) % 100 == 0:
                elapsed = time.perf_counter() - t_start
                rate = (i + 1) / elapsed
                logger.info("Progress: %d/%d (%.1f/s)", i + 1, len(safety_records), rate)

            sample_data = sample_index.get(rec["task_name"], {}).get(rec.get("sample_id", ""), {})
            entry = {
                "sample_id": rec.get("sample_id", ""),
                "task_name": rec["task_name"],
                "model": rec["model"],
                "backend_label": rec.get("backend_label", rec.get("backend", "")),
                "quant": rec.get("quant", ""),
            }

            try:
                task = rec["task_name"]
                candidate = rec.get("candidate", "")

                if task in ("advbench_refusal", "jailbreak_amplification"):
                    prompt = sample_data.get("instruction", rec.get("sample_id", ""))
                    result = judge.judge_refusal(prompt, candidate)
                elif task == "truthfulqa":
                    question = sample_data.get("question", "")
                    correct = sample_data.get("correct_answers", [])
                    incorrect = sample_data.get("incorrect_answers", [])
                    result = judge.judge_truthfulness(question, candidate, correct, incorrect)
                elif task == "bbq_bias":
                    result = judge.judge_bias(
                        context=sample_data.get("context", ""),
                        question=sample_data.get("question", ""),
                        response=candidate,
                        choice_a=sample_data.get("answer_choice_0", ""),
                        choice_b=sample_data.get("answer_choice_1", ""),
                        choice_c=sample_data.get("answer_choice_2", ""),
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
                logger.warning("Judge failed: %s/%s/%s: %s",
                             rec["model"], rec.get("backend_label"), rec.get("sample_id"), e)
                entry["judge_label"] = "ERROR"
                entry["judge_raw_response"] = str(e)
                entry["judge_model"] = judge.model
                entry["judge_parse_success"] = False
                entry["judge_elapsed_ms"] = 0.0
                parse_failures += 1

            f.write(json.dumps(entry, default=str) + "\n")
            judged += 1

    elapsed_total = time.perf_counter() - t_start
    logger.info("Done: %d judged, %d parse failures, %.1fm", judged, parse_failures, elapsed_total / 60)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="TR136 LLM judge")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--run-dir", type=str, default=None)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if args.run_dir:
        run_dir = Path(args.run_dir)
    else:
        run_dir = find_latest_run("research/tr136/results")

    if not run_dir or not run_dir.exists():
        logger.error("No run directory found")
        return 1

    return run_judge(run_dir, limit=args.limit)


if __name__ == "__main__":
    sys.exit(main())
