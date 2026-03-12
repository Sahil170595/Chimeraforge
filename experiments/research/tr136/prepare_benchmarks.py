"""TR136: Prepare safety + capability benchmarks (copy from TR134 Phase 3).

Copies safety tasks (AdvBench, TruthfulQA, BBQ, jailbreak) and capability
controls (MMLU, ARC-Challenge) from TR134 Phase 3.

Usage:
    python research/tr136/prepare_benchmarks.py [-v] [--force]
"""

from __future__ import annotations

import argparse
import logging
import random
import shutil
from pathlib import Path
import sys

import yaml

_DIR = Path(__file__).resolve().parent
_TASKS_DIR = _DIR / "tasks"
_REPO = _DIR.parents[1]

logger = logging.getLogger("tr136.prepare_benchmarks")

_TR134_TASKS = _REPO / "research" / "tr134" / "phase3" / "tasks"

# Safety tasks to copy verbatim
_SAFETY_TASKS = [
    "advbench_refusal.yaml",
    "truthfulqa.yaml",
    "bbq_bias.yaml",
    "jailbreak_amplification.yaml",
]

# Capability tasks to copy (ARC verbatim, MMLU subsampled to 200)
MMLU_CONTROL_N = 200


def _copy_task_files(force: bool) -> int:
    """Copy TR134 safety + ARC task YAMLs verbatim."""
    files_to_copy = _SAFETY_TASKS + ["arc_challenge.yaml"]
    copied = 0
    for fname in files_to_copy:
        src = _TR134_TASKS / fname
        dst = _TASKS_DIR / fname
        if dst.exists() and not force:
            logger.info("Already exists: %s", dst.name)
            continue
        if not src.exists():
            logger.error("Source not found: %s", src)
            return -1
        shutil.copy2(src, dst)
        logger.info("Copied %s", fname)
        copied += 1
    return copied


def _generate_mmlu_control(force: bool) -> bool:
    """Generate MMLU subset (200 questions) for capability control."""
    dst = _TASKS_DIR / "mmlu_real.yaml"
    if dst.exists() and not force:
        logger.info("Already exists: %s", dst.name)
        return True

    src = _TR134_TASKS / "mmlu_real.yaml"
    if not src.exists():
        logger.error("TR134 MMLU not found: %s", src)
        return False

    with open(src, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    samples = data.get("samples", [])
    if len(samples) > MMLU_CONTROL_N:
        rng = random.Random(42)
        samples = rng.sample(samples, MMLU_CONTROL_N)

    data["samples"] = samples
    data["description"] = (
        f"MMLU subset ({MMLU_CONTROL_N} questions) — capability control for TR136 "
        "cross-backend safety experiment."
    )

    with open(dst, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    logger.info("Generated %s (%d samples)", dst.name, len(samples))
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="TR136 benchmark preparation")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    _TASKS_DIR.mkdir(parents=True, exist_ok=True)

    n_copied = _copy_task_files(force=args.force)
    if n_copied < 0:
        return 1

    mmlu_ok = _generate_mmlu_control(force=args.force)

    logger.info(
        "Done: %d files copied, MMLU control: %s",
        n_copied, "ok" if mmlu_ok else "FAILED",
    )
    return 0 if mmlu_ok else 1


if __name__ == "__main__":
    sys.exit(main())
