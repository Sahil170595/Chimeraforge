"""TR132 — Continuous Batching Deep Dive orchestrator.

Runs the full pipeline:
  Phase 1 (validation gate) → Phase 2 (vLLM profiled) →
  Phase 3 (TGI profiled) → Phase 4 (TR131 cross-reference) →
  Phase 5 (analysis).

Usage:
    python -m research.tr132.run -v
    python -m research.tr132.run --phase1-only
    python -m research.tr132.run --analyze-only
    python -m research.tr132.run --skip-tgi
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

from research.tr132.shared.utils import TR132_RESULTS, capture_environment

log = logging.getLogger("tr132")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="TR132: Continuous Batching Deep Dive pipeline",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument(
        "--phase1-only", action="store_true", help="Run Phase 1 validation only"
    )
    parser.add_argument(
        "--analyze-only",
        action="store_true",
        help="Skip data collection, run analysis on latest run",
    )
    parser.add_argument("--skip-tgi", action="store_true", help="Skip Phase 3 (TGI)")
    parser.add_argument("--skip-vllm", action="store_true", help="Skip Phase 2 (vLLM)")
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

    # ── Analyze-only mode ──
    if args.analyze_only:
        log.info("--analyze-only: running analysis on latest run")
        from research.tr132.shared.utils import find_latest_run

        run_dir = find_latest_run(TR132_RESULTS)
        if run_dir is None:
            log.error("No existing run found in %s", TR132_RESULTS)
            return 1
        log.info("Analyzing: %s", run_dir)
        from research.tr132.analyze import run_analysis

        run_analysis(run_dir, alpha=cfg.get("phase5", {}).get("alpha", 0.05))
        return 0

    # ── Create run directory ──
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = TR132_RESULTS / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # ── Manifest ──
    start_time = datetime.now(UTC).isoformat()
    manifest = {
        "run_id": run_id,
        "experiment": "tr132",
        "config": cfg,
        "environment": capture_environment(),
        "start_time": start_time,
    }

    log.info("=" * 60)
    log.info("TR132: Continuous Batching Deep Dive")
    log.info("  Models: %s", [m["name"] for m in cfg["models"]])
    log.info("  Backends: %s", list(cfg["backends"].keys()))
    log.info("  Run dir: %s", run_dir)
    log.info("=" * 60)

    # ── Phase 1: Validation Gate ──
    log.info("-" * 40)
    log.info("Phase 1: Validation Gate")
    log.info("-" * 40)

    from research.tr132.run_validation import run_phase1

    validation = run_phase1(cfg, run_dir)

    # Save validation results
    with open(run_dir / "validation.json", "w", encoding="utf-8") as f:
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

    log.info("Phase 1 PASSED — nsys captures Docker GPU kernels")

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

    # ── Phase 2: vLLM Profiled ──
    vllm_results = None
    if not args.skip_vllm:
        log.info("-" * 40)
        log.info("Phase 2: vLLM Profiled (N=1 and N=8)")
        log.info("-" * 40)

        from research.tr132.run_serving_profiled import run_serving_profiled

        vllm_results = run_serving_profiled(
            cfg,
            run_dir,
            backend_name="vllm",
            phase_label="p2_vllm",
        )
    else:
        log.info("Skipping Phase 2 (--skip-vllm)")

    # ── Phase 3: TGI Profiled ──
    tgi_results = None
    if not args.skip_tgi:
        log.info("-" * 40)
        log.info("Phase 3: TGI Profiled (N=1 and N=8)")
        log.info("-" * 40)

        from research.tr132.run_serving_profiled import run_serving_profiled

        tgi_results = run_serving_profiled(
            cfg,
            run_dir,
            backend_name="tgi",
            phase_label="p3_tgi",
        )
    else:
        log.info("Skipping Phase 3 (--skip-tgi)")

    # ── Phase 4: TR131 Cross-Reference ──
    log.info("-" * 40)
    log.info("Phase 4: TR131 Cross-Reference")
    log.info("-" * 40)

    from research.tr132.shared.cross_reference import load_tr131_data

    tr131_results_dir = cfg.get("phase4", {}).get("tr131_results_dir")
    if tr131_results_dir:
        tr131_results_dir = _REPO / tr131_results_dir
    tr131_data = load_tr131_data(results_dir=tr131_results_dir)

    with open(run_dir / "p4_tr131_crossref.json", "w", encoding="utf-8") as f:
        # Strip raw_data from metrics for serialization
        save_data = {k: v for k, v in tr131_data.items() if k != "raw_data"}
        json.dump(save_data, f, indent=2, default=str)

    log.info("TR131 cross-reference: %s", tr131_data.get("status", "unknown"))

    # ── Phase 5: Analysis ──
    log.info("-" * 40)
    log.info("Phase 5: Analysis")
    log.info("-" * 40)

    # Finalize manifest before analysis
    manifest["end_time"] = datetime.now(UTC).isoformat()
    manifest["validation"] = {k: v for k, v in validation.items() if k != "parsed_data"}
    manifest["status"] = "complete"

    try:
        from research.tr132.analyze import run_analysis

        run_analysis(
            run_dir,
            vllm_results=vllm_results,
            tgi_results=tgi_results,
            tr131_data=tr131_data,
            alpha=cfg.get("phase5", {}).get("alpha", 0.05),
        )
        manifest["analysis_status"] = "complete"
    except Exception as e:
        log.error("Analysis failed: %s", e, exc_info=True)
        manifest["analysis_status"] = f"failed: {e}"

    with open(run_dir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, default=str)

    log.info("=" * 60)
    log.info("TR132 complete: %s", run_dir)
    log.info("=" * 60)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
