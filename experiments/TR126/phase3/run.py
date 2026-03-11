#!/usr/bin/env python3
"""TR126 Phase 3: Backend Matrix Rerun under Linux

Usage:
    python research/tr126/phase3/run.py [-v] [--skip-ollama-setup]

Steps:
  1. Start Ollama server + pull models (if not skipped)
  2. Run backend matrix
  3. Analyze results
  4. Generate report
"""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import time

_DIR = Path(__file__).resolve().parent
_REPO = _DIR.parents[2]


def _start_ollama() -> subprocess.Popen | None:
    """Start Ollama server in background. Returns Popen or None."""
    try:
        import requests

        resp = requests.get("http://localhost:11434/api/tags", timeout=3)
        if resp.ok:
            print("  Ollama already running.")
            return None
    except Exception:
        pass

    print("  Starting Ollama server...")
    proc = subprocess.Popen(
        ["ollama", "serve"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    # Wait for server to start
    for _ in range(30):
        try:
            import requests

            resp = requests.get("http://localhost:11434/api/tags", timeout=2)
            if resp.ok:
                print("  Ollama server started.")
                return proc
        except Exception:
            time.sleep(1)

    print("  WARNING: Ollama may not have started.")
    return proc


def _pull_models() -> None:
    """Pull required Ollama models for Phase 3."""
    models = ["qwen2.5:0.5b", "qwen2.5:1.5b", "qwen2.5:3b", "llama3.2:1b"]
    for model in models:
        print(f"  Pulling {model}...")
        subprocess.run(["ollama", "pull", model], timeout=600)


def main() -> int:
    skip_setup = "--skip-ollama-setup" in sys.argv
    verbose = "-v" in sys.argv
    v_flag = ["-v"] if verbose else []

    print("=" * 60)
    print("TR126 Phase 3: Backend Matrix Rerun")
    print("=" * 60)

    ollama_proc = None
    if not skip_setup:
        print("\n--- Step 1/4: Ollama Setup ---")
        ollama_proc = _start_ollama()
        _pull_models()
    else:
        print("\n--- Skipping Ollama setup ---")

    try:
        # Step 2: Run matrix
        print("\n--- Step 2/4: Run Matrix ---")
        result = subprocess.run(
            [sys.executable, str(_DIR / "run_matrix.py"), *v_flag],
            cwd=str(_REPO),
        )
        if result.returncode != 0:
            print(f"ERROR: Matrix run failed (exit {result.returncode})")
            return result.returncode

        # Step 3: Analyze
        print("\n--- Step 3/4: Analysis ---")
        result = subprocess.run(
            [sys.executable, str(_DIR / "analyze.py"), *v_flag],
            cwd=str(_REPO),
        )
        if result.returncode != 0:
            print(f"WARNING: Analysis failed (exit {result.returncode})")

        # Step 4: Report
        print("\n--- Step 4/4: Report ---")
        result = subprocess.run(
            [sys.executable, str(_DIR / "generate_report.py"), *v_flag],
            cwd=str(_REPO),
        )
        if result.returncode != 0:
            print(f"WARNING: Report generation failed (exit {result.returncode})")

    finally:
        if ollama_proc:
            print("\nStopping Ollama server...")
            ollama_proc.terminate()

    print("\n" + "=" * 60)
    print("Phase 3 complete.")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
