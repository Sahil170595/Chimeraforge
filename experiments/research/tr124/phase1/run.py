"""TR124 Phase 1: Run backend quality comparison.

Usage:
    python research/tr124/phase1/run.py [-v]

Calls the shared eval framework runner with the Phase 1 config.
Results go to results/eval/tr124_phase1/<timestamp>/.

Phase 1 was completed 2026-02-18 in ~3 hours on RTX 4080.
2,800 samples: 400 generation + 2,400 benchmark.
"""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

_DIR = Path(__file__).resolve().parent
_REPO = _DIR.parents[2]


def main() -> int:
    cmd = [
        sys.executable,
        "-m",
        "scripts.eval.runner",
        "--config",
        str(_DIR / "config.yaml"),
    ]
    if "-v" in sys.argv or "--verbose" in sys.argv:
        cmd.append("-v")

    print(f"Running: {' '.join(cmd)}")
    print(f"CWD: {_REPO}")
    result = subprocess.run(cmd, cwd=_REPO)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
