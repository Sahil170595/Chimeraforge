"""TR131 — GPU Profiling orchestrator.

Runs the full pipeline:
  Pre-flight → Phase 1 (validation) → Phase 2 (Ollama N=1) →
  Phase 3 (Ollama N=8) → Phase 4 (PyTorch N=1) →
  Phase 5 (PyTorch N=8) → Phase 6 (ncu targeted) → analyze.

Usage:
    python research/tr131/run.py -v
    python research/tr131/run.py --phase1-only
    python research/tr131/run.py --analyze-only
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
import logging
from pathlib import Path
import sys

import yaml

_DIR = Path(__file__).resolve().parent
_REPO = _DIR.parents[1]

sys.path.insert(0, str(_REPO))

from research.tr131.shared.utils import (
    TR131_RESULTS,
    capture_environment,
)

log = logging.getLogger("tr131")


def main() -> int:
    parser = argparse.ArgumentParser(description="TR131 GPU Profiling pipeline")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument(
        "--phase1-only", action="store_true", help="Run Phase 1 validation only"
    )
    parser.add_argument(
        "--analyze-only",
        action="store_true",
        help="Skip data collection, run analysis only",
    )
    parser.add_argument(
        "--skip-pytorch", action="store_true", help="Skip PyTorch direct phases (4-5)"
    )
    parser.add_argument(
        "--skip-ncu", action="store_true", help="Skip Nsight Compute phase (6)"
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

    if args.analyze_only:
        log.info("Skipping data collection (--analyze-only)")
        # TODO: run analyze.py
        return 0

    # ── Create run directory ──
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = TR131_RESULTS / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # ── Manifest ──
    start_time = datetime.now(UTC).isoformat()
    manifest = {
        "run_id": run_id,
        "experiment": "tr131",
        "config": cfg,
        "environment": capture_environment(),
        "start_time": start_time,
    }

    log.info("=" * 60)
    log.info("TR131: GPU Profiling — Root-Cause Analysis")
    log.info("  Models: %s", [m["name"] for m in cfg["models"]])
    log.info("  Run dir: %s", run_dir)
    log.info("=" * 60)

    # ── Phase 1: Validation ──
    log.info("-" * 40)
    log.info("Phase 1: nsys Validation")
    log.info("-" * 40)

    from research.tr131.run_validation import run_phase1

    validation = run_phase1(cfg, run_dir)

    # Save validation results
    with open(run_dir / "validation.json", "w", encoding="utf-8") as f:
        # Remove non-serializable parsed_data for the saved version
        save_val = {k: v for k, v in validation.items() if k != "parsed_data"}
        json.dump(save_val, f, indent=2, default=str)

    if not validation["gate_passed"]:
        log.error("Phase 1 validation FAILED — cannot proceed")
        log.error("Errors: %s", validation.get("errors", []))
        manifest["end_time"] = datetime.now(UTC).isoformat()
        manifest["validation"] = {
            k: v for k, v in validation.items() if k != "parsed_data"
        }
        manifest["status"] = "validation_failed"
        with open(run_dir / "manifest.json", "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, default=str)
        return 1

    log.info("Phase 1 PASSED — nsys captures Ollama CUDA kernels")

    if args.phase1_only:
        log.info("--phase1-only: stopping after validation")
        manifest["end_time"] = datetime.now(UTC).isoformat()
        manifest["validation"] = {
            k: v for k, v in validation.items() if k != "parsed_data"
        }
        manifest["status"] = "phase1_only"
        with open(run_dir / "manifest.json", "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, default=str)
        return 0

    # ── Phase 2: Ollama N=1 ──
    log.info("-" * 40)
    log.info("Phase 2: Ollama N=1 Profiled")
    log.info("-" * 40)

    from research.tr131.run_ollama_profiled import run_ollama_profiled

    run_ollama_profiled(cfg, run_dir, n_agents=1, phase="p2_ollama_n1")

    # ── Phase 3: Ollama N=8 ──
    log.info("-" * 40)
    log.info("Phase 3: Ollama N=8 Profiled")
    log.info("-" * 40)

    run_ollama_profiled(cfg, run_dir, n_agents=8, phase="p3_ollama_n8")

    # ── Phase 4-5: PyTorch Direct ──
    if not args.skip_pytorch:
        log.info("-" * 40)
        log.info("Phase 4-5: PyTorch Direct (N=1 and N=8)")
        log.info("-" * 40)

        from research.tr131.run_pytorch_direct import run_pytorch_profiled

        run_pytorch_profiled(cfg, run_dir, n_threads=1, phase="p4_pytorch_n1")
        run_pytorch_profiled(cfg, run_dir, n_threads=8, phase="p5_pytorch_n8")
    else:
        log.info("Skipping PyTorch phases (--skip-pytorch)")

    # ── Phase 6: ncu ──
    if not args.skip_ncu:
        log.info("-" * 40)
        log.info("Phase 6: Nsight Compute Targeted")
        log.info("-" * 40)
        try:
            from research.tr131.run_ncu_targeted import run_ncu_targeted

            run_ncu_targeted(cfg, run_dir)
        except Exception as e:
            log.warning("Phase 6 failed (non-fatal): %s", e)
    else:
        log.info("Skipping ncu phase (--skip-ncu)")

    # ── Finalize ──
    manifest["end_time"] = datetime.now(UTC).isoformat()
    manifest["validation"] = {k: v for k, v in validation.items() if k != "parsed_data"}
    manifest["status"] = "complete"
    with open(run_dir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, default=str)

    log.info("=" * 60)
    log.info("TR131 data collection complete: %s", run_dir)
    log.info("=" * 60)

    # ── Analyze ──
    log.info("Running analysis...")
    try:
        from research.tr131.analyze import run_analysis

        run_analysis(run_dir)
    except Exception as e:
        log.error("Analysis failed: %s", e)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
