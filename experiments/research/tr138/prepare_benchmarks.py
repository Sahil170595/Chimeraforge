"""TR138: Prepare safety & capability benchmark task YAMLs.

Reuses TR134 Phase 3 benchmark generators. Copies task files to
research/tr138/tasks/ for TR-isolated reproducibility.
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import shutil
from pathlib import Path
import sys

_DIR = Path(__file__).resolve().parent
_TASKS_DIR = _DIR / "tasks"
_REPO = _DIR.parents[1]

if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

logger = logging.getLogger("tr138.prepare_benchmarks")

# Source tasks from TR134 Phase 3 (canonical safety benchmarks)
_TR134_TASKS_DIR = _REPO / "research" / "tr134" / "phase3" / "tasks"

EXPECTED_TASKS = [
    "advbench_refusal.yaml",
    "truthfulqa.yaml",
    "bbq_bias.yaml",
    "jailbreak_amplification.yaml",
    "mmlu_real.yaml",
    "arc_challenge.yaml",
]


def _file_hash(path: Path) -> str:
    """SHA256 hash (first 16 chars)."""
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()[:16]


def _ensure_tr134_tasks_exist() -> bool:
    """Check that TR134 Phase 3 tasks exist (prerequisite)."""
    for name in EXPECTED_TASKS:
        src = _TR134_TASKS_DIR / name
        if not src.exists():
            logger.error(
                "TR134 task file missing: %s — run TR134 prepare_benchmarks first",
                src,
            )
            return False
    return True


def _copy_tasks(force: bool = False) -> int:
    """Copy task YAMLs from TR134 to TR138 tasks directory."""
    _TASKS_DIR.mkdir(parents=True, exist_ok=True)
    copied = 0

    for name in EXPECTED_TASKS:
        src = _TR134_TASKS_DIR / name
        dst = _TASKS_DIR / name

        if dst.exists() and not force:
            logger.debug("Task already exists: %s (hash=%s)", name, _file_hash(dst))
            continue

        shutil.copy2(src, dst)
        copied += 1
        logger.info("Copied %s (hash=%s)", name, _file_hash(dst))

    return copied


def main() -> int:
    parser = argparse.ArgumentParser(
        description="TR138: Prepare benchmark task YAMLs (copy from TR134)",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing task files",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Pre-flight: check TR134 tasks exist
    if not _ensure_tr134_tasks_exist():
        logger.error(
            "TR134 Phase 3 tasks not found. Run:\n"
            "  python research/tr134/phase3/prepare_benchmarks.py\n"
            "before running TR138."
        )
        return 1

    # Copy tasks
    n_copied = _copy_tasks(force=args.force)
    logger.info("Copied %d task files to %s", n_copied, _TASKS_DIR)

    # Verify all present
    missing = []
    for name in EXPECTED_TASKS:
        path = _TASKS_DIR / name
        if not path.exists():
            missing.append(name)
        else:
            logger.info("  %-35s hash=%s", name, _file_hash(path))

    if missing:
        logger.error("Missing task files: %s", missing)
        return 1

    logger.info("All %d task files ready.", len(EXPECTED_TASKS))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
