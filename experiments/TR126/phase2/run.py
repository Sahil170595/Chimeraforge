#!/usr/bin/env python3
"""TR126 Phase 2: Compile Paradox Replication under Linux + Triton

Usage:
    python research/tr126/phase2/run.py [-v] [--skip-ablations]

Steps:
  1. Run baseline compile experiment (config.yaml)
  2. Run padded shapes ablation (config_padded.yaml)
  3. Run dynamic shapes ablation (config_dynamic.yaml)
  4. Analyze results
  5. Generate report
"""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

_DIR = Path(__file__).resolve().parent
_REPO = _DIR.parents[2]


def main() -> int:
    verbose = "-v" in sys.argv
    skip_ablations = "--skip-ablations" in sys.argv
    v_flag = ["-v"] if verbose else []

    print("=" * 60)
    print("TR126 Phase 2: Compile Paradox Replication")
    print("=" * 60)

    configs = [("baseline", _DIR / "config.yaml")]
    if not skip_ablations:
        configs.append(("padded", _DIR / "config_padded.yaml"))
        configs.append(("dynamic", _DIR / "config_dynamic.yaml"))

    # Steps 1-3: Run experiments
    for label, config_path in configs:
        print(f"\n--- Running {label}: {config_path.name} ---")
        result = subprocess.run(
            [
                sys.executable,
                str(_DIR / "run_compile.py"),
                "--config",
                str(config_path),
                *v_flag,
            ],
            cwd=str(_REPO),
        )
        if result.returncode != 0:
            print(f"ERROR: {label} experiment failed (exit {result.returncode})")
            if label == "baseline":
                return result.returncode
            # Ablation failures are non-fatal
            print("  Continuing with remaining experiments...")

    # Step 4: Analyze
    print("\n--- Step 4/5: Analysis ---")
    result = subprocess.run(
        [sys.executable, str(_DIR / "analyze.py"), *v_flag],
        cwd=str(_REPO),
    )
    if result.returncode != 0:
        print(f"WARNING: Analysis failed (exit {result.returncode})")

    # Step 5: Report
    print("\n--- Step 5/5: Report Generation ---")
    result = subprocess.run(
        [sys.executable, str(_DIR / "generate_report.py"), *v_flag],
        cwd=str(_REPO),
    )
    if result.returncode != 0:
        print(f"WARNING: Report generation failed (exit {result.returncode})")

    print("\n" + "=" * 60)
    print("Phase 2 complete.")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
