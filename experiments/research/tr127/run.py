"""TR127 — Main orchestrator.

Runs the full pipeline: Ollama setup → context sweep → analysis → report.

Usage:
    python research/tr127/run.py -v
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
import subprocess
import sys
import time

import requests
import yaml

_DIR = Path(__file__).resolve().parent
_REPO = _DIR.parents[1]

log = logging.getLogger("tr127")


def _check_ollama() -> bool:
    """Check if Ollama is running.  Returns True if reachable."""
    try:
        resp = requests.get("http://localhost:11434/api/tags", timeout=3)
        return resp.ok
    except Exception:
        return False


def _start_ollama() -> subprocess.Popen | None:
    """Start Ollama server if not already running."""
    if _check_ollama():
        log.info("Ollama already running")
        return None

    log.info("Starting Ollama server...")
    proc = subprocess.Popen(
        ["ollama", "serve"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(30):
        if _check_ollama():
            log.info("Ollama started")
            return proc
        time.sleep(1)

    log.warning("Ollama may not have started properly")
    return proc


def _pull_ollama_models(config_path: str) -> None:
    """Pull all required Ollama models from config, skip already-present."""
    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    # Collect tags from config
    tags = [m["ollama_tag"] for m in cfg.get("models", []) if m.get("ollama_tag")]
    if not tags:
        log.info("No Ollama models in config — skipping pull")
        return

    # Check which are already present
    try:
        resp = requests.get("http://localhost:11434/api/tags", timeout=5)
        resp.raise_for_status()
        local_models = {m["name"] for m in resp.json().get("models", [])}
    except Exception:
        local_models = set()

    for tag in tags:
        # Ollama tags in /api/tags include ":latest" suffix sometimes
        present = any(tag in name or name.startswith(tag) for name in local_models)
        if present:
            log.info("  %s — already pulled", tag)
            continue

        log.info("  Pulling %s ...", tag)
        try:
            ret = subprocess.run(
                ["ollama", "pull", tag],
                timeout=600,
                capture_output=True,
                text=True,
            )
            if ret.returncode != 0:
                log.error("  Failed to pull %s: %s", tag, ret.stderr.strip())
            else:
                log.info("  %s — pulled successfully", tag)
        except subprocess.TimeoutExpired:
            log.error("  Timeout pulling %s (>600s)", tag)
        except FileNotFoundError:
            log.error("  'ollama' command not found — cannot pull models")
            return


def main() -> int:
    parser = argparse.ArgumentParser(description="TR127 full pipeline")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument(
        "--skip-sweep",
        action="store_true",
        help="Skip sweep, run analysis + report on latest",
    )
    parser.add_argument(
        "--skip-ollama-setup",
        action="store_true",
        help="Skip Ollama server start and model pulling",
    )
    parser.add_argument(
        "--config", default=str(_DIR / "config.yaml"), help="Path to config.yaml"
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s  %(message)s",
    )

    v_flag = ["-v"] if args.verbose else []
    ollama_proc = None

    try:
        # Step 0: Ollama setup
        if not args.skip_ollama_setup:
            log.info("=" * 60)
            log.info("Step 0: Ollama setup")
            log.info("=" * 60)
            ollama_proc = _start_ollama()
            _pull_ollama_models(args.config)
        else:
            log.info("Skipping Ollama setup (--skip-ollama-setup)")

        # Step 1: Run context sweep
        if not args.skip_sweep:
            log.info("=" * 60)
            log.info("Step 1/3: Running context sweep")
            log.info("=" * 60)
            ret = subprocess.run(
                [
                    sys.executable,
                    str(_DIR / "run_context_sweep.py"),
                    "--config",
                    args.config,
                    *v_flag,
                ],
                cwd=str(_REPO),
            )
            if ret.returncode != 0:
                log.error("Context sweep failed (exit %d)", ret.returncode)
                return ret.returncode
        else:
            log.info("Skipping sweep (--skip-sweep)")

        # Step 2: Analyze
        log.info("=" * 60)
        log.info("Step 2/3: Analyzing results")
        log.info("=" * 60)
        ret = subprocess.run(
            [sys.executable, str(_DIR / "analyze.py"), *v_flag],
            cwd=str(_REPO),
        )
        if ret.returncode != 0:
            log.error("Analysis failed (exit %d)", ret.returncode)
            return ret.returncode

        # Step 3: Generate report
        log.info("=" * 60)
        log.info("Step 3/3: Generating report")
        log.info("=" * 60)
        ret = subprocess.run(
            [sys.executable, str(_DIR / "generate_report.py"), *v_flag],
            cwd=str(_REPO),
        )
        if ret.returncode != 0:
            log.error("Report generation failed (exit %d)", ret.returncode)
            return ret.returncode

        log.info("=" * 60)
        log.info("TR127 pipeline complete!")
        log.info("=" * 60)
        return 0

    finally:
        if ollama_proc is not None:
            log.info("Stopping Ollama server")
            ollama_proc.terminate()


if __name__ == "__main__":
    raise SystemExit(main())
