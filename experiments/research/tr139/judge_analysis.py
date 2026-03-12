"""TR139: Post-hoc LLM judge scoring for multi-turn conversations.

Judges the target turn (final harmful request) and any turn where the
regex classifier detected compliance.  Reuses TR134's LLM judge
infrastructure (Qwen 2.5 7B @ Q8_0).
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

from research.tr134.shared.llm_judge import LLMJudge
from research.tr139.shared.utils import find_latest_run

logger = logging.getLogger("tr139.judge_analysis")

# Judge configuration
JUDGE_MODEL = "qwen2.5:7b-instruct-q8_0"
JUDGE_OLLAMA_URL = "http://localhost:11434"
JUDGE_TIMEOUT_S = 120


def _load_conversations(samples_path: Path) -> list[dict]:
    """Load conversation records from samples.jsonl."""
    records = []
    with open(samples_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if rec.get("status") == "ok":
                records.append(rec)
    logger.info("Loaded %d conversations for judging", len(records))
    return records


def _judge_conversation(judge: LLMJudge, rec: dict) -> list[dict]:
    """Judge critical turns in a conversation.

    Judges:
    1. The target turn (is_target=True) — always judged
    2. Any turn where refusal_score < 1.0 — potential compliance

    Returns list of judge label dicts (one per judged turn).
    """
    results = []
    turns = rec.get("turns", [])
    behavior = rec.get("behavior", "")

    judged_turn_nums = set()

    for turn_data in turns:
        turn_num = turn_data.get("turn", 0)
        is_target = turn_data.get("is_target", False)
        refusal_score = turn_data.get("refusal_score", 1.0)
        response = turn_data.get("assistant_response", "")

        # Judge target turns and compliance turns
        should_judge = is_target or refusal_score < 1.0
        if not should_judge or not response.strip():
            continue
        if turn_num in judged_turn_nums:
            continue
        judged_turn_nums.add(turn_num)

        # Build prompt context: the user message for this turn
        user_msg = turn_data.get("user_message", behavior)

        try:
            result = judge.judge_refusal(user_msg, response)
        except Exception as exc:
            logger.warning(
                "Judge failed for %s turn %d: %s",
                rec.get("behavior_id"),
                turn_num,
                exc,
            )
            continue

        results.append({
            "behavior_id": rec.get("behavior_id", ""),
            "behavior_category": rec.get("behavior_category", ""),
            "model": rec.get("model", ""),
            "quant": rec.get("quant", ""),
            "phase": rec.get("phase", 0),
            "attack_strategy": rec.get("attack_strategy", ""),
            "turn": turn_num,
            "is_target": is_target,
            "judge_label": result.label,
            "judge_raw": result.raw_response[:500],
            "judge_model": result.judge_model,
            "judge_parse_success": result.parse_success,
            "judge_elapsed_ms": result.elapsed_ms,
        })

    return results


def main() -> int:
    parser = argparse.ArgumentParser(
        description="TR139: LLM judge scoring for multi-turn conversations",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--run-dir", type=str, default=None)
    parser.add_argument(
        "--max-conversations",
        type=int,
        default=0,
        help="Max conversations to judge (0 = all)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Find run directory
    output_base = _REPO / "research" / "tr139" / "results"
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

    # Load conversations
    conversations = _load_conversations(samples_path)
    if not conversations:
        logger.warning("No conversations to judge")
        return 0

    if args.max_conversations > 0:
        conversations = conversations[: args.max_conversations]
        logger.info("Limiting to %d conversations", len(conversations))

    # Initialize judge
    try:
        judge = LLMJudge(
            model=JUDGE_MODEL,
            ollama_url=JUDGE_OLLAMA_URL,
            timeout_s=JUDGE_TIMEOUT_S,
        )
    except Exception as exc:
        logger.error("Failed to initialize LLM judge: %s", exc)
        logger.info("Judge analysis is optional -- continuing without judge labels")
        return 0

    # Judge all conversations
    judge_path = run_dir / "judge_labels.jsonl"
    n_judged = 0
    n_failed = 0

    with open(judge_path, "w", encoding="utf-8") as f:
        for i, rec in enumerate(conversations):
            turn_results = _judge_conversation(judge, rec)
            for result in turn_results:
                f.write(json.dumps(result, default=str) + "\n")
                n_judged += 1

            if not turn_results:
                n_failed += 1

            if (i + 1) % 50 == 0:
                logger.info(
                    "  Judged %d/%d conversations (%.0f%%, %d labels so far)",
                    i + 1,
                    len(conversations),
                    100 * (i + 1) / len(conversations),
                    n_judged,
                )

    logger.info(
        "Judge analysis complete: %d labels from %d conversations, "
        "%d failed, written to %s",
        n_judged,
        len(conversations),
        n_failed,
        judge_path,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
