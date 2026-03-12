"""TR125 Phase 2: Run production-grade quantization decision matrix evaluation.

Usage:
    python research/tr125/phase2/run.py [-v] [--skip-prep]

Steps:
  1. Prepare benchmarks + pull Ollama models (idempotent, skipped if already done)
  2. Run eval framework with Phase 2 config (34 models × 7 tasks)
  3. Run Phase 2-specific analysis
  4. Generate Phase 2 report

Estimated runtime: ~8-10 hours on RTX 4080 (24,990 samples).
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

    # Step 1: Prepare benchmarks + Ollama models (both idempotent)
    if not skip_prep:
        print("=== Step 1: Preparing benchmarks + Ollama models ===")

        bench_cmd = [sys.executable, str(_DIR / "prepare_benchmarks.py")]
        if verbose:
            bench_cmd.append("-v")
        result = subprocess.run(bench_cmd, cwd=_REPO)
        if result.returncode != 0:
            print("ERROR: Benchmark preparation failed")
            return result.returncode

        setup_cmd = [sys.executable, str(_DIR / "setup_ollama.py")]
        if verbose:
            setup_cmd.append("-v")
        result = subprocess.run(setup_cmd, cwd=_REPO)
        if result.returncode != 0:
            print("WARNING: Some models may be missing. Continuing anyway...")

    # Step 2: Run evaluation
    print("\n=== Step 2: Running evaluation (24,990 samples) ===")
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
    if result.returncode != 0:
        print("ERROR: Analysis failed")
        return result.returncode

    # Step 4: Generate report
    print("\n=== Step 4: Generating report ===")
    report_cmd = [sys.executable, str(_DIR / "generate_report.py")]
    if verbose:
        report_cmd.append("-v")

    result = subprocess.run(report_cmd, cwd=_REPO)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
