"""TR129 — N-Agent Scaling Laws orchestrator.

Runs the full pipeline:
  Ollama setup → pre-flight → warmup →
  Phase 1 (baseline) → Phase 2 (N-agent scaling) →
  Phase 3 (think-time sweep) → Phase 4 (heterogeneous) →
  analyze → report.

Key design: Phase 4 requires restarting Ollama with OLLAMA_MAX_LOADED_MODELS=3
so all 3 models are pre-loaded for heterogeneous multi-model tests.

Usage:
    python research/tr129/run.py -v
    python research/tr129/run.py --skip-phases --analyze-only
"""

from __future__ import annotations

import argparse
import csv
from datetime import UTC, datetime
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import time

import requests
import yaml

_DIR = Path(__file__).resolve().parent
_REPO = _DIR.parents[1]

sys.path.insert(0, str(_REPO))

from research.tr126.shared.env_fingerprint import capture_environment
from research.tr129.run_baseline import run_phase1
from research.tr129.run_heterogeneous import run_phase4
from research.tr129.run_scaling import run_phase2
from research.tr129.run_think_time import run_phase3
from research.tr129.shared.utils import CSV_FIELDNAMES, TR129_RESULTS

log = logging.getLogger("tr129")


# ── Ollama management ────────────────────────────────────────────────


def _check_ollama(url: str = "http://localhost:11434") -> bool:
    """Check if Ollama is running and responsive."""
    try:
        resp = requests.get(f"{url}/api/tags", timeout=3)
        return resp.ok
    except Exception:
        return False


def _stop_ollama() -> None:
    """Stop any running Ollama process."""
    try:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/F", "/IM", "ollama.exe"],
                capture_output=True,
                timeout=10,
            )
            subprocess.run(
                ["taskkill", "/F", "/IM", "ollama_llama_server.exe"],
                capture_output=True,
                timeout=10,
            )
        else:
            subprocess.run(
                ["pkill", "-f", "ollama serve"],
                capture_output=True,
                timeout=10,
            )
    except Exception as exc:
        log.debug("Stop Ollama: %s", exc)
    time.sleep(2)


def _start_ollama(
    url: str = "http://localhost:11434",
    extra_env: dict[str, str] | None = None,
) -> subprocess.Popen | None:
    """Start Ollama server with optional extra environment variables.

    Returns the Popen object.
    """
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
        log.info("Starting Ollama with extra env: %s", extra_env)
    else:
        log.info("Starting Ollama (default config)")

    proc = subprocess.Popen(
        ["ollama", "serve"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
    )

    for _ in range(30):
        if _check_ollama(url):
            log.info("Ollama started (pid=%d)", proc.pid)
            return proc
        time.sleep(1)

    log.warning("Ollama may not have started properly")
    return proc


def _restart_ollama(
    url: str = "http://localhost:11434",
    extra_env: dict[str, str] | None = None,
) -> subprocess.Popen | None:
    """Stop Ollama, then restart with optional env vars."""
    log.info("Restarting Ollama...")
    _stop_ollama()
    time.sleep(3)
    return _start_ollama(url=url, extra_env=extra_env)


def _pull_ollama_models(cfg: dict) -> None:
    """Pull all required Ollama models, skip already-present."""
    url = cfg["ollama_url"]
    tags = [m["ollama_tag"] for m in cfg.get("models", []) if m.get("ollama_tag")]
    if not tags:
        return

    try:
        resp = requests.get(f"{url}/api/tags", timeout=5)
        resp.raise_for_status()
        local_models = {m["name"] for m in resp.json().get("models", [])}
    except Exception:
        local_models = set()

    for tag in tags:
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
                log.info("  %s — pulled", tag)
        except subprocess.TimeoutExpired:
            log.error("  Timeout pulling %s (>600s)", tag)
        except FileNotFoundError:
            log.error("  'ollama' command not found")
            return


# ── Pre-flight & warmup ──────────────────────────────────────────────


def _preflight_validation(cfg: dict) -> dict:
    """Pre-flight environment checks before measurement."""
    validation = {"checks": [], "warnings": []}
    url = cfg["ollama_url"]

    try:
        resp = requests.get(f"{url}/api/tags", timeout=5)
        resp.raise_for_status()
        tags_data = resp.json()
        available_models = {m["name"] for m in tags_data.get("models", [])}
        validation["ollama_reachable"] = True
        validation["available_models"] = sorted(available_models)
    except Exception as exc:
        validation["ollama_reachable"] = False
        validation["warnings"].append(f"Ollama not reachable: {exc}")
        return validation

    required = [m["ollama_tag"] for m in cfg.get("models", [])]
    for tag in required:
        found = any(tag in name or name.startswith(tag) for name in available_models)
        if not found:
            validation["warnings"].append(f"Model {tag} not found in Ollama")
        validation["checks"].append({"model": tag, "available": found})

    # nvidia-smi check
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,driver_version",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            parts = [p.strip() for p in result.stdout.strip().split(",")]
            validation["gpu_name"] = parts[0] if len(parts) > 0 else "unknown"
            validation["gpu_vram_mb"] = int(parts[1]) if len(parts) > 1 else 0
            validation["gpu_driver"] = parts[2] if len(parts) > 2 else "unknown"
        else:
            validation["warnings"].append("nvidia-smi returned non-zero")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        validation["warnings"].append("nvidia-smi not available")

    return validation


def _warmup(cfg: dict, models: list[dict] | None = None) -> dict:
    """Send warmup requests to each model; returns timing info."""
    url = cfg["ollama_url"]
    timeout = cfg.get("ollama_timeout_s", 120)
    n_warmup = cfg.get("warmup_requests", 3)
    if models is None:
        models = cfg["models"]
    warmup_results = {}

    for model_cfg in models:
        tag = model_cfg["ollama_tag"]
        log.info("  Warming up %s (%d requests)...", tag, n_warmup)
        timings = []

        for i in range(n_warmup):
            t0 = time.perf_counter()
            try:
                resp = requests.post(
                    f"{url}/api/generate",
                    json={
                        "model": tag,
                        "prompt": "Hello, this is a warmup request.",
                        "stream": False,
                        "options": {"num_predict": 10},
                    },
                    timeout=timeout,
                )
                elapsed_ms = (time.perf_counter() - t0) * 1000
                if resp.ok:
                    timings.append(elapsed_ms)
                    log.info("  %s warmup %d: %.0f ms", tag, i + 1, elapsed_ms)
                else:
                    log.warning(
                        "  %s warmup %d status %d", tag, i + 1, resp.status_code
                    )
            except Exception as exc:
                elapsed_ms = (time.perf_counter() - t0) * 1000
                log.warning(
                    "  %s warmup %d failed (%.0f ms): %s", tag, i + 1, elapsed_ms, exc
                )

        warmup_results[tag] = {
            "n": n_warmup,
            "ok": len(timings),
            "timings_ms": [round(t, 1) for t in timings],
        }

    return warmup_results


# ── Main ─────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description="TR129 full pipeline")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument(
        "--skip-phases",
        action="store_true",
        help="Skip data collection, run analysis + report only",
    )
    parser.add_argument(
        "--skip-ollama-setup",
        action="store_true",
        help="Skip Ollama server start and model pulling",
    )
    parser.add_argument(
        "--analyze-only", action="store_true", help="Alias for --skip-phases"
    )
    parser.add_argument(
        "--config", default=str(_DIR / "config.yaml"), help="Path to config.yaml"
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s  %(message)s",
    )

    with open(args.config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    skip_phases = args.skip_phases or args.analyze_only
    ollama_proc = None

    try:
        # ── Step 0: Ollama setup ──
        if not skip_phases and not args.skip_ollama_setup:
            log.info("=" * 60)
            log.info("Step 0: Ollama setup")
            log.info("=" * 60)
            ollama_proc = _start_ollama(url=cfg["ollama_url"])
            _pull_ollama_models(cfg)
        elif not skip_phases:
            log.info("Skipping Ollama setup (--skip-ollama-setup)")

        # ── Step 1: Data collection ──
        if not skip_phases:
            log.info("=" * 60)
            log.info("Step 1/3: Running phases 1-4")
            log.info("=" * 60)

            # Pre-flight
            log.info("Running pre-flight validation...")
            preflight = _preflight_validation(cfg)
            for w in preflight.get("warnings", []):
                log.warning("  PRE-FLIGHT: %s", w)

            # Create run directory
            run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
            run_dir = TR129_RESULTS / run_id
            run_dir.mkdir(parents=True, exist_ok=True)

            # Warmup
            log.info("Warming up models...")
            warmup_info = _warmup(cfg)

            # Write manifest
            start_time = datetime.now(UTC).isoformat()
            manifest = {
                "run_id": run_id,
                "experiment": "tr129",
                "config": cfg,
                "environment": capture_environment(),
                "preflight_validation": preflight,
                "warmup": warmup_info,
                "start_time": start_time,
            }

            csv_path = run_dir / "metrics.csv"
            total_rows = 0
            phase_rows = {}

            with open(csv_path, "w", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(
                    fh,
                    fieldnames=CSV_FIELDNAMES,
                    extrasaction="ignore",
                )
                writer.writeheader()

                # ── Phase 1: Single-agent baseline ──
                log.info("-" * 40)
                log.info("Phase 1: Single-agent baseline (N=1)")
                log.info("-" * 40)
                n = run_phase1(cfg, run_dir, writer)
                phase_rows["p1_baseline"] = n
                total_rows += n
                fh.flush()

                # ── Phase 2: N-agent scaling (CORE) ──
                log.info("-" * 40)
                log.info("Phase 2: N-agent scaling sweep (CORE)")
                log.info("-" * 40)
                n = run_phase2(cfg, run_dir, writer)
                phase_rows["p2_scaling"] = n
                total_rows += n
                fh.flush()

                # ── Phase 3: Think-time sweep ──
                log.info("-" * 40)
                log.info("Phase 3: Think-time sweep (N=4)")
                log.info("-" * 40)
                n = run_phase3(cfg, run_dir, writer)
                phase_rows["p3_think_time"] = n
                total_rows += n
                fh.flush()

                # ── Phase 4: Heterogeneous multi-model ──
                log.info("-" * 40)
                log.info("Phase 4: Heterogeneous multi-model agents")
                log.info("-" * 40)

                # Restart Ollama with OLLAMA_MAX_LOADED_MODELS=3
                max_loaded = cfg["phase4"].get("ollama_max_loaded_models", 3)
                if ollama_proc is not None:
                    ollama_proc.terminate()
                    ollama_proc = None
                    time.sleep(3)
                _stop_ollama()

                ollama_proc = _restart_ollama(
                    url=cfg["ollama_url"],
                    extra_env={"OLLAMA_MAX_LOADED_MODELS": str(max_loaded)},
                )

                # Warmup all 3 models to pre-load into VRAM
                log.info("  Warming up all models for Phase 4...")
                _warmup(cfg)

                n = run_phase4(cfg, run_dir, writer)
                phase_rows["p4_heterogeneous"] = n
                total_rows += n

            # Row count validation
            log.info("Row counts by phase:")
            for phase, count in phase_rows.items():
                log.info("  %s: %d rows", phase, count)
                if count == 0:
                    log.warning("  WARNING: Phase %s produced 0 rows!", phase)

            # Finalize manifest
            manifest["end_time"] = datetime.now(UTC).isoformat()
            manifest["total_rows"] = total_rows
            manifest["rows_per_phase"] = phase_rows
            with open(run_dir / "manifest.json", "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2, default=str)

            log.info("Data collection complete: %d rows -> %s", total_rows, csv_path)
        else:
            log.info("Skipping phases (--skip-phases)")

        # ── Step 2: Analyze ──
        log.info("=" * 60)
        log.info("Step 2/3: Analyzing results")
        log.info("=" * 60)
        v_flag = ["-v"] if args.verbose else []
        ret = subprocess.run(
            [sys.executable, str(_DIR / "analyze.py"), *v_flag],
            cwd=str(_REPO),
        )
        if ret.returncode != 0:
            log.error("Analysis failed (exit %d)", ret.returncode)
            return ret.returncode

        # ── Step 3: Report ──
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
        log.info("TR129 pipeline complete!")
        log.info("=" * 60)
        return 0

    finally:
        if ollama_proc is not None:
            log.info("Stopping Ollama server")
            ollama_proc.terminate()


if __name__ == "__main__":
    raise SystemExit(main())
