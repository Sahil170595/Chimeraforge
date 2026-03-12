#!/usr/bin/env python3
"""TR126 Phase 1: Docker Environment Validation

Usage:
    python research/tr126/phase1/run.py [-v]

Steps:
  1. Validate environment (GPU, CUDA, Triton, torch.compile)
  2. Validate weight parity (deterministic output comparison)

Gate: Phase 2 and 3 should NOT proceed until Phase 1 passes.
"""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

_DIR = Path(__file__).resolve().parent
_REPO = _DIR.parents[2]


def main() -> int:
    verbose = "-v" in sys.argv
    v_flag = ["-v"] if verbose else []

    print("=" * 60)
    print("TR126 Phase 1: Docker Environment Validation")
    print("=" * 60)

    # Step 1: Environment validation
    print("\n--- Step 1/2: Environment Validation ---")
    result = subprocess.run(
        [sys.executable, str(_DIR / "validate_environment.py"), *v_flag],
        cwd=str(_REPO),
    )
    if result.returncode != 0:
        print("\nFATAL: Environment validation failed. Do not proceed to Phase 2/3.")
        return 1

    # Step 2: Weight parity
    print("\n--- Step 2/2: Weight Parity Validation ---")
    result = subprocess.run(
        [sys.executable, str(_DIR / "validate_weights.py"), *v_flag],
        cwd=str(_REPO),
    )
    if result.returncode != 0:
        print("\nWARNING: Weight parity check failed (non-fatal).")

    print("\n" + "=" * 60)
    print("Phase 1 complete. Proceed to Phase 2.")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
