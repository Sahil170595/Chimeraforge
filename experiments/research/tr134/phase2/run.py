"""TR134 Phase 2: Run full alignment robustness under quantization matrix.

Usage:
    python research/tr134/phase2/run.py [-v] [--skip-prep]

Steps:
  1. Prepare benchmarks (safety + capability, idempotent)
  2. Run eval framework with Phase 2 config (14 model×quant × 5 tasks)
  3. Run Phase 2-specific degradation analysis
  4. Generate Phase 2 report

Estimated runtime: ~4-6 hours on RTX 4080 (~9,590 samples).
"""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

_DIR = Path(__file__).resolve().parent
_REPO = _DIR.parents[2]


def main() -> int:
    skip_prep = "--skip-prep" in sys.argv
    verbose = "-v" in sys.argv or "--verbose" in sys.argv

    # Step 1: Prepare benchmarks
    if not skip_prep:
        print("=== Step 1: Preparing safety + capability benchmarks ===")
        bench_cmd = [sys.executable, str(_DIR / "prepare_benchmarks.py")]
        if verbose:
            bench_cmd.append("-v")
        result = subprocess.run(bench_cmd, cwd=_REPO)
        if result.returncode != 0:
            print("ERROR: Benchmark preparation failed")
            return result.returncode

    # Step 2: Run evaluation
    print("\n=== Step 2: Running evaluation (~9,590 samples) ===")
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

    # Step 3: Phase-specific degradation analysis
    print("\n=== Step 3: Running Phase 2 degradation analysis ===")
    analyze_cmd = [sys.executable, str(_DIR / "analyze.py")]
    if verbose:
        analyze_cmd.append("-v")

    result = subprocess.run(analyze_cmd, cwd=_REPO)
    if result.returncode != 0:
        print("ERROR: Analysis failed")
        return result.returncode

    # Step 4: Generate report
    print("\n=== Step 4: Generating Phase 2 report ===")
    report_cmd = [sys.executable, str(_DIR / "generate_report.py")]
    if verbose:
        report_cmd.append("-v")

    result = subprocess.run(report_cmd, cwd=_REPO)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
