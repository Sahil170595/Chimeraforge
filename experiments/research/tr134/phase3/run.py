"""TR134 Phase 3: Run multi-family alignment robustness under quantization.

Usage:
    python research/tr134/phase3/run.py [-v] [--skip-prep] [--skip-eval] [--skip-judge]

Steps:
  1. Prepare benchmarks (safety + capability + jailbreak, idempotent)
  2. Run eval framework with Phase 3 config (26 model×quant × 6 tasks)
  3. Run LLM judge post-hoc analysis
  4. Run Phase 3-specific degradation analysis (14 passes, reads judge output)
  5. Generate Phase 3 report (18 sections)

Estimated runtime: ~6h eval + ~4h judge = ~10h on RTX 4080 (~24,830 samples).
"""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

_DIR = Path(__file__).resolve().parent
_REPO = _DIR.parents[2]


def main() -> int:
    skip_prep = "--skip-prep" in sys.argv
    skip_eval = "--skip-eval" in sys.argv
    skip_judge = "--skip-judge" in sys.argv
    verbose = "-v" in sys.argv or "--verbose" in sys.argv

    # Step 1: Prepare benchmarks
    if not skip_prep:
        print("=== Step 1: Preparing safety + capability + jailbreak benchmarks ===")
        bench_cmd = [sys.executable, str(_DIR / "prepare_benchmarks.py")]
        if verbose:
            bench_cmd.append("-v")
        result = subprocess.run(bench_cmd, cwd=_REPO)
        if result.returncode != 0:
            print("ERROR: Benchmark preparation failed")
            return result.returncode

    # Step 2: Run evaluation
    if not skip_eval:
        print("\n=== Step 2: Running evaluation (~31,515 samples) ===")
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

    # Step 3: LLM judge post-hoc analysis (before analyze so Pass 13 can read results)
    if not skip_judge:
        print("\n=== Step 3: Running LLM judge post-hoc analysis ===")
        judge_cmd = [sys.executable, str(_DIR / "judge_analysis.py")]
        if verbose:
            judge_cmd.append("-v")

        result = subprocess.run(judge_cmd, cwd=_REPO)
        if result.returncode != 0:
            print("WARNING: Judge analysis failed (non-fatal, report will note missing judge data)")

    # Step 4: Phase-specific degradation analysis (14 passes)
    print("\n=== Step 4: Running Phase 3 degradation analysis (14 passes) ===")
    analyze_cmd = [sys.executable, str(_DIR / "analyze.py")]
    if verbose:
        analyze_cmd.append("-v")

    result = subprocess.run(analyze_cmd, cwd=_REPO)
    if result.returncode != 0:
        print("ERROR: Analysis failed")
        return result.returncode

    # Step 5: Generate report
    print("\n=== Step 5: Generating Phase 3 report (18 sections) ===")
    report_cmd = [sys.executable, str(_DIR / "generate_report.py")]
    if verbose:
        report_cmd.append("-v")

    result = subprocess.run(report_cmd, cwd=_REPO)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
