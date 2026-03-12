"""TR138: Post-hoc LLM judge scoring for safety samples.

Reuses TR134's LLM judge infrastructure (Qwen 2.5 7B @ Q8_0).
Judges only safety-domain records from the eval run.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import sys

_DIR = Path(__file__).resolve().parent
_REPO = _DIR.parents[1]

if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from research.tr134.shared.llm_judge import LLMJudge, JudgeResult
from research.tr138.shared.utils import SAFETY_TASKS, find_latest_run

logger = logging.getLogger("tr138.judge_analysis")

# Judge configuration
JUDGE_MODEL = "qwen2.5:7b-instruct-q8_0"
JUDGE_OLLAMA_URL = "http://localhost:11434"
JUDGE_TIMEOUT_S = 120


def _load_safety_records(samples_path: Path) -> list[dict]:
    """Load only safety-domain records from samples.jsonl."""
    records = []
    with open(samples_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            task = rec.get("task_name", "")
            if task in SAFETY_TASKS and rec.get("status") == "ok":
                records.append(rec)
    logger.info("Loaded %d safety records for judging", len(records))
    return records


def _judge_record(judge: LLMJudge, rec: dict) -> dict | None:
    """Judge a single record, return judge label dict or None on failure."""
    task = rec.get("task_name", "")
    candidate = rec.get("candidate", "")
    prompt = rec.get("prompt", "")

    if not candidate.strip():
        return None

    try:
        if task in ("advbench_refusal", "jailbreak_amplification"):
            result = judge.judge_refusal(prompt, candidate)
        elif task == "truthfulqa":
            result = judge.judge_truthfulness(prompt, candidate)
        elif task == "bbq_bias":
            result = judge.judge_bias(prompt, candidate)
        else:
            return None
    except Exception as exc:
        logger.warning("Judge failed for %s: %s", rec.get("sample_id"), exc)
        return None

    return {
        "sample_id": rec.get("sample_id", ""),
        "task_name": task,
        "phase": rec.get("phase", 0),
        "batch_size": rec.get("batch_size", 0),
        "model": rec.get("model", ""),
        "condition": rec.get("condition", rec.get("co_batch_condition", "")),
        "co_batch_condition": rec.get("co_batch_condition", ""),
        "quant": rec.get("quant", ""),
        "concurrency": rec.get("concurrency", 0),
        "judge_label": result.label,
        "judge_raw": result.raw_response[:500],
        "judge_model": result.judge_model,
        "judge_parse_success": result.parse_success,
        "judge_elapsed_ms": result.elapsed_ms,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="TR138: LLM judge scoring for safety samples",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--run-dir", type=str, default=None)
    parser.add_argument(
        "--max-samples",
        type=int,
        default=0,
        help="Max samples to judge (0 = all)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Find run directory
    output_base = _REPO / "research" / "tr138" / "results"
    if args.run_dir:
        run_dir = Path(args.run_dir)
    else:
        run_dir = find_latest_run(output_base)

    if run_dir is None or not run_dir.exists():
        logger.error("No run directory found in %s", output_base)
        return 1

    samples_path = run_dir / "samples.jsonl"
    if not samples_path.exists():
        logger.error("samples.jsonl not found in %s", run_dir)
        return 1

    # Load safety records
    records = _load_safety_records(samples_path)
    if not records:
        logger.warning("No safety records to judge")
        return 0

    if args.max_samples > 0:
        records = records[: args.max_samples]
        logger.info("Limiting to %d samples", len(records))

    # Initialize judge
    try:
        judge = LLMJudge(
            model=JUDGE_MODEL,
            ollama_url=JUDGE_OLLAMA_URL,
            timeout_s=JUDGE_TIMEOUT_S,
        )
    except Exception as exc:
        logger.error("Failed to initialize LLM judge: %s", exc)
        logger.info("Judge analysis is optional — continuing without judge labels")
        return 0

    # Judge all records
    judge_path = run_dir / "judge_labels.jsonl"
    n_judged = 0
    n_failed = 0

    with open(judge_path, "w", encoding="utf-8") as f:
        for i, rec in enumerate(records):
            result = _judge_record(judge, rec)
            if result is not None:
                f.write(json.dumps(result, default=str) + "\n")
                n_judged += 1
            else:
                n_failed += 1

            if (i + 1) % 100 == 0:
                logger.info(
                    "  Judged %d/%d (%.0f%%, %d failed)",
                    i + 1,
                    len(records),
                    100 * (i + 1) / len(records),
                    n_failed,
                )

    logger.info(
        "Judge analysis complete: %d judged, %d failed, written to %s",
        n_judged,
        n_failed,
        judge_path,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
