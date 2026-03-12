"""TR133 — Predictive Capacity Planner orchestrator.

Runs the full pipeline:
  1. Load data from TR123-TR132
  2. Train/val split
  3. Fit all 6 predictive models
  4. Serialize fitted models
  5. Run validation (analyze.py)
  6. Save manifest

Usage:
    python -m research.tr133.run -v
    python -m research.tr133.run --analyze-only
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

from research.tr133.shared.utils import (
    TR133_RESULTS,
    capture_environment,
    find_latest_run,
)

log = logging.getLogger("tr133")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="TR133: Predictive Capacity Planner pipeline",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument(
        "--analyze-only",
        action="store_true",
        help="Skip fitting, run analysis on latest run",
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

    # ── Analyze-only mode ──
    if args.analyze_only:
        log.info("--analyze-only: running analysis on latest run")
        run_dir = find_latest_run(TR133_RESULTS)
        if run_dir is None:
            log.error("No existing run found in %s", TR133_RESULTS)
            return 1
        log.info("Analyzing: %s", run_dir)
        from research.tr133.analyze import run_analysis

        run_analysis(run_dir, cfg)
        return 0

    # ── Create run directory ──
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = TR133_RESULTS / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    start_time = datetime.now(UTC).isoformat()
    manifest = {
        "run_id": run_id,
        "experiment": "tr133",
        "config": cfg,
        "environment": capture_environment(),
        "start_time": start_time,
    }

    log.info("=" * 60)
    log.info("TR133: Predictive Capacity Planner")
    log.info("  Run dir: %s", run_dir)
    log.info("=" * 60)

    # ── Phase 1: Load data ──
    log.info("-" * 40)
    log.info("Phase 1/5: Loading data from TR123-TR130")
    log.info("-" * 40)

    from research.tr133.shared.data_loader import load_all, train_val_split

    dataset = load_all(cfg)

    manifest["data_summary"] = {
        "throughput_records": len(dataset.throughput),
        "quality_records": len(dataset.quality),
        "vram_records": len(dataset.vram),
        "latency_records": len(dataset.latency),
        "cost_records": len(dataset.cost),
        "scaling_records": len(dataset.scaling),
    }

    total = sum(manifest["data_summary"].values())
    log.info("Total records loaded: %d", total)

    if total == 0:
        log.error("No data loaded -- check data source paths in config.yaml")
        manifest["status"] = "no_data"
        manifest["end_time"] = datetime.now(UTC).isoformat()
        with open(run_dir / "manifest.json", "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, default=str)
        return 1

    # ── Phase 2: Train/val split ──
    log.info("-" * 40)
    log.info("Phase 2/5: Train/validation split")
    log.info("-" * 40)

    seed = cfg.get("validation", {}).get("random_seed", 42)
    train_frac = cfg.get("validation", {}).get("train_fraction", 0.80)

    from research.tr133.shared.data_loader import PlannerDataset

    train_ds = PlannerDataset()
    val_ds = PlannerDataset()

    for attr in ["throughput", "quality", "vram", "latency", "cost", "scaling"]:
        records = getattr(dataset, attr)
        train, val = train_val_split(records, train_frac=train_frac, seed=seed)
        setattr(train_ds, attr, train)
        setattr(val_ds, attr, val)
        log.info("  %s: %d train, %d val", attr, len(train), len(val))

    # Save splits summary
    splits = {
        attr: {"train": len(getattr(train_ds, attr)), "val": len(getattr(val_ds, attr))}
        for attr in ["throughput", "quality", "vram", "latency", "cost", "scaling"]
    }
    with open(run_dir / "splits.json", "w", encoding="utf-8") as f:
        json.dump(splits, f, indent=2)

    # ── Phase 3: Fit models ──
    log.info("-" * 40)
    log.info("Phase 3/5: Fitting 6 predictive models")
    log.info("-" * 40)

    from research.tr133.shared.models import fit_all_models, serialize_models

    models = fit_all_models(train_ds)

    # ── Phase 4: Serialize ──
    log.info("-" * 40)
    log.info("Phase 4/5: Serializing fitted models")
    log.info("-" * 40)

    models_path = run_dir / "fitted_models.json"
    serialize_models(models, models_path)

    # ── Phase 5: Validation ──
    log.info("-" * 40)
    log.info("Phase 5/5: Validation & analysis")
    log.info("-" * 40)

    try:
        from research.tr133.analyze import run_analysis

        analysis = run_analysis(run_dir, cfg, models=models, val_ds=val_ds)
        manifest["analysis_status"] = "complete"
        manifest["validation_summary"] = analysis.get("summary", {})
    except Exception as e:
        log.error("Analysis failed: %s", e, exc_info=True)
        manifest["analysis_status"] = f"failed: {e}"

    # ── Save manifest ──
    manifest["end_time"] = datetime.now(UTC).isoformat()
    manifest["status"] = "complete"
    with open(run_dir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, default=str)

    log.info("=" * 60)
    log.info("TR133 complete: %s", run_dir)
    log.info("=" * 60)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
