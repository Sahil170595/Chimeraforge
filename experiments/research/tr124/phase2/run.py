"""TR124 Phase 2: Run quantization quality evaluation.

Usage:
    python research/tr124/phase2/run.py [-v] [--skip-setup]

Steps:
  1. Verify/pull Ollama models (setup_ollama.py)
  2. Run eval framework with Phase 2 config
  3. Run Phase 2-specific analysis

Estimated runtime: ~4-5 hours on RTX 4080 (8 models × 5 tasks × 10 samples).
"""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

_DIR = Path(__file__).resolve().parent
_REPO = _DIR.parents[2]


def main() -> int:
    skip_setup = "--skip-setup" in sys.argv
    verbose = "-v" in sys.argv or "--verbose" in sys.argv

    # Step 1: Setup Ollama models
    if not skip_setup:
        print("=== Step 1: Verifying Ollama models ===")
        setup_cmd = [sys.executable, str(_DIR / "setup_ollama.py")]
        if verbose:
            setup_cmd.append("-v")
        result = subprocess.run(setup_cmd, cwd=_REPO)
        if result.returncode != 0:
            print("WARNING: Some models failed to pull. Continuing anyway...")

    # Step 2: Run evaluation
    print("\n=== Step 2: Running evaluation ===")
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

    # Step 3: Phase-specific analysis
    print("\n=== Step 3: Running Phase 2 analysis ===")
    analyze_cmd = [sys.executable, str(_DIR / "analyze.py")]
    if verbose:
        analyze_cmd.append("-v")

    result = subprocess.run(analyze_cmd, cwd=_REPO)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
