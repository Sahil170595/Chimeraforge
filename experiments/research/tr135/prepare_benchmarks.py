"""TR135: Prepare safety + capability benchmarks.

Copies TR134 Phase 3 safety task files (AdvBench, TruthfulQA, BBQ, jailbreak)
and generates MMLU (200 questions) + ARC-Challenge (200 questions) for
capability control.

Usage:
    python research/tr135/prepare_benchmarks.py [-v] [--force]
"""

from __future__ import annotations

import argparse
import logging
import shutil
from pathlib import Path
import sys

import yaml

_DIR = Path(__file__).resolve().parent
_TASKS_DIR = _DIR / "tasks"
_REPO = _DIR.parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

logger = logging.getLogger("tr135.prepare_benchmarks")

# Source task directory from TR134 Phase 3
_TR134_TASKS = _REPO / "research" / "tr134" / "phase3" / "tasks"

# Safety tasks to copy verbatim from TR134
_SAFETY_TASKS = [
    "advbench_refusal.yaml",
    "truthfulqa.yaml",
    "bbq_bias.yaml",
    "jailbreak_amplification.yaml",
]

# MMLU: 200 for meaningful per-subject breakdown
MMLU_CONTROL_N = 200


def _copy_safety_tasks(force: bool = False) -> int:
    """Copy TR134 safety task YAMLs to TR135 tasks dir."""
    copied = 0
    for fname in _SAFETY_TASKS:
        src = _TR134_TASKS / fname
        dst = _TASKS_DIR / fname
        if dst.exists() and not force:
            logger.info("Already exists: %s (use --force to overwrite)", dst.name)
            continue
        if not src.exists():
            logger.error("Source not found: %s", src)
            continue
        shutil.copy2(src, dst)
        logger.info("Copied %s", fname)
        copied += 1
    return copied


def _generate_mmlu_control(force: bool = False) -> bool:
    """Generate MMLU task for capability control."""
    dst = _TASKS_DIR / "mmlu_real.yaml"
    if dst.exists() and not force:
        logger.info("Already exists: %s", dst.name)
        return True

    # Load TR134's MMLU and subsample
    src = _TR134_TASKS / "mmlu_real.yaml"
    if not src.exists():
        logger.error("TR134 MMLU not found: %s", src)
        return False

    with open(src, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    samples = data.get("samples", [])
    if len(samples) > MMLU_CONTROL_N:
        import random
        rng = random.Random(42)
        samples = rng.sample(samples, MMLU_CONTROL_N)

    data["samples"] = samples
    data["description"] = (
        f"MMLU subset ({MMLU_CONTROL_N} questions) — capability control for TR135 "
        "concurrency x safety experiment."
    )

    with open(dst, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    logger.info("Generated %s (%d samples)", dst.name, len(samples))
    return True


def _copy_arc_challenge(force: bool = False) -> bool:
    """Copy ARC-Challenge task from TR134 Phase 3."""
    dst = _TASKS_DIR / "arc_challenge.yaml"
    if dst.exists() and not force:
        logger.info("Already exists: %s", dst.name)
        return True

    src = _TR134_TASKS / "arc_challenge.yaml"
    if not src.exists():
        logger.error("TR134 ARC-Challenge not found: %s", src)
        return False

    shutil.copy2(src, dst)
    logger.info("Copied arc_challenge.yaml (%s)", src)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="TR135 benchmark preparation")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--force", action="store_true", help="Overwrite existing task files")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    _TASKS_DIR.mkdir(parents=True, exist_ok=True)

    n_copied = _copy_safety_tasks(force=args.force)
    mmlu_ok = _generate_mmlu_control(force=args.force)
    arc_ok = _copy_arc_challenge(force=args.force)

    logger.info(
        "Done: %d safety tasks copied, MMLU: %s, ARC: %s",
        n_copied, "ok" if mmlu_ok else "FAILED", "ok" if arc_ok else "FAILED",
    )
    return 0 if (mmlu_ok and arc_ok) else 1


if __name__ == "__main__":
    sys.exit(main())
