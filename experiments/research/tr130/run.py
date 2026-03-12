"""TR130 — Serving Stack Benchmarking orchestrator.

Runs the full pipeline:
  Pre-flight → Phase 1 (validation) → Phase 2 (baseline) →
  Phase 3 (N-agent scaling) → Phase 4 (TTFT) → analyze → report.

Only one backend runs at a time (sequential — they compete for GPU).
Backends: Ollama (native), vLLM (Docker), TGI (Docker).

Usage:
    python research/tr130/run.py -v
    python research/tr130/run.py --skip-phases --analyze-only
"""

from __future__ import annotations

import argparse
import csv
from datetime import UTC, datetime
import json
import logging
from pathlib import Path
import subprocess
import sys

import yaml

_DIR = Path(__file__).resolve().parent
_REPO = _DIR.parents[1]

sys.path.insert(0, str(_REPO))

from research.tr130.run_baseline import run_phase2
from research.tr130.run_scaling import run_phase3
from research.tr130.run_ttft import run_phase4
from research.tr130.run_validation import run_phase1
from research.tr130.shared.docker_utils import docker_available
from research.tr130.shared.utils import CSV_FIELDNAMES, TR130_RESULTS

log = logging.getLogger("tr130")


# ── Pre-flight ──────────────────────────────────────────────────────


def _preflight_validation(cfg: dict) -> dict:
    """Pre-flight environment checks before measurement."""
    validation = {"checks": [], "warnings": []}

    # 1. Docker
    if docker_available():
        validation["docker"] = True
    else:
        validation["docker"] = False
        validation["warnings"].append("Docker not available — vLLM and TGI will fail")

    # 2. nvidia-smi
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

    # 3. Ollama
    try:
        import urllib.request

        resp = urllib.request.urlopen("http://localhost:11434/api/tags", timeout=3)
        validation["ollama_reachable"] = resp.status == 200
    except Exception:
        validation["ollama_reachable"] = False
        validation["warnings"].append("Ollama not reachable — will attempt to start")

    # 4. HF_TOKEN check for gated models
    import os

    hf_token = os.environ.get("HF_TOKEN", "")
    gated = [m["name"] for m in cfg.get("models", []) if m.get("gated")]
    if gated and not hf_token:
        validation["warnings"].append(
            f"HF_TOKEN not set — gated models may fail: {gated}"
        )
    validation["hf_token_set"] = bool(hf_token)

    return validation


def _capture_environment() -> dict:
    """Capture basic environment fingerprint."""
    import platform

    env = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "machine": platform.machine(),
    }

    # GPU info
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
            env["gpu_name"] = parts[0] if len(parts) > 0 else "unknown"
            env["gpu_vram_mb"] = parts[1] if len(parts) > 1 else "unknown"
            env["gpu_driver"] = parts[2] if len(parts) > 2 else "unknown"
    except Exception:
        pass

    # Docker version
    try:
        result = subprocess.run(
            ["docker", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            env["docker_version"] = result.stdout.strip()
    except Exception:
        pass

    return env


# ── Main ─────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description="TR130 full pipeline")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument(
        "--skip-phases",
        action="store_true",
        help="Skip data collection, run analysis + report only",
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

    # ── Step 0: Data collection ──
    if not skip_phases:
        log.info("=" * 60)
        log.info("TR130: Serving Stack Benchmarking")
        log.info("  Backends: Ollama, vLLM, TGI")
        log.info("  Models: %s", [m["name"] for m in cfg["models"]])
        log.info("=" * 60)

        # Pre-flight
        log.info("Running pre-flight validation...")
        preflight = _preflight_validation(cfg)
        for w in preflight.get("warnings", []):
            log.warning("  PRE-FLIGHT: %s", w)

        # Create run directory
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir = TR130_RESULTS / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        # Write manifest
        start_time = datetime.now(UTC).isoformat()
        manifest = {
            "run_id": run_id,
            "experiment": "tr130",
            "config": cfg,
            "environment": _capture_environment(),
            "preflight_validation": preflight,
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

            # ── Phase 1: Environment Validation ──
            log.info("-" * 40)
            log.info("Phase 1: Environment Validation")
            log.info("-" * 40)
            n, skip_list = run_phase1(cfg, run_dir, writer)
            phase_rows["p1_validation"] = n
            total_rows += n
            fh.flush()
            if skip_list:
                log.warning(
                    "Phase 1 skip list (%d combos): %s",
                    len(skip_list),
                    skip_list,
                )

            # ── Phase 2: Single-Agent Baseline ──
            log.info("-" * 40)
            log.info("Phase 2: Single-Agent Baseline (N=1)")
            log.info("-" * 40)
            n = run_phase2(cfg, run_dir, writer, skip_list=skip_list)
            phase_rows["p2_baseline"] = n
            total_rows += n
            fh.flush()

            # ── Phase 3: N-Agent Scaling (CORE) ──
            log.info("-" * 40)
            log.info("Phase 3: N-Agent Scaling (CORE)")
            log.info("-" * 40)
            n = run_phase3(cfg, run_dir, writer, skip_list=skip_list)
            phase_rows["p3_scaling"] = n
            total_rows += n
            fh.flush()

            # ── Phase 4: TTFT Streaming Comparison ──
            log.info("-" * 40)
            log.info("Phase 4: TTFT Streaming Comparison")
            log.info("-" * 40)
            n = run_phase4(cfg, run_dir, writer, skip_list=skip_list)
            phase_rows["p4_ttft"] = n
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
        manifest["skip_list"] = [{"backend": b, "model": m} for b, m in skip_list]
        with open(run_dir / "manifest.json", "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, default=str)

        log.info(
            "Data collection complete: %d rows -> %s",
            total_rows,
            csv_path,
        )
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
    log.info("TR130 pipeline complete!")
    log.info("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
