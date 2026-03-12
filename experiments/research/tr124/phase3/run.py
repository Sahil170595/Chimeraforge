"""TR124 Phase 3: Run sampling variance evaluation.

Usage:
    python research/tr124/phase3/run.py [-v]

Steps:
  1. Run eval framework with Phase 3 config (temp=0.7, 5 reps)
  2. Run Phase 3-specific variance analysis

Estimated runtime: ~3-4 hours on RTX 4080
(2 models × 2 backends × 3 tasks × 10 samples × 5 reps = 600 generations).
"""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

_DIR = Path(__file__).resolve().parent
_REPO = _DIR.parents[2]


def main() -> int:
    verbose = "-v" in sys.argv or "--verbose" in sys.argv

    # Step 1: Run evaluation
    print("=== Step 1: Running evaluation (temp=0.7, 5 reps) ===")
    eval_cmd = [
        sys.executable,
        "-m",
        "scripts.eval.runner",
        "--config",
        str(_DIR / "config.yaml"),
    ]
    if verbose:
        eval_cmd.append("-v")

    result = subprocess.run(eval_cmd, cwd=_REPO)
    if result.returncode != 0:
        print("ERROR: Evaluation failed")
        return result.returncode

    # Step 2: Phase-specific analysis
    print("\n=== Step 2: Running Phase 3 variance analysis ===")
    analyze_cmd = [sys.executable, str(_DIR / "analyze.py")]
    if verbose:
        analyze_cmd.append("-v")

    result = subprocess.run(analyze_cmd, cwd=_REPO)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
