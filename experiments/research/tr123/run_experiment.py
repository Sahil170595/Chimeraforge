#!/usr/bin/env python3
"""
TR123: KV-Cache Production Economics — Experiment Orchestrator.

Runs the full pipeline:
  1. smoke_test.py         → go/no-go
  2. run_benchmark.py      → raw_measurements.jsonl
  3. validate.py           → quality report
  4. kv_cache_analysis.py  → memory overhead tables
  5. analyze_results.py    → cost tables
  6. cross_reference_tr119 → improvement ratios
  7. visualize.py          → plots/
  8. generate_report.py    → Technical_Report_123.md
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
import sys

logger = logging.getLogger(__name__)

TR123_DIR = Path(__file__).parent
DEFAULT_CONFIG = TR123_DIR / "configs" / "matrix.yaml"


def main():
    parser = argparse.ArgumentParser(description="TR123: Full Experiment Pipeline")
    parser.add_argument(
        "--config",
        type=str,
        default=str(DEFAULT_CONFIG),
        help="Path to matrix.yaml config",
    )
    parser.add_argument(
        "--skip-smoke",
        action="store_true",
        help="Skip smoke test (use if you've already validated)",
    )
    parser.add_argument(
        "--skip-benchmark",
        action="store_true",
        help="Skip benchmark (use to re-analyze existing results)",
    )
    parser.add_argument(
        "--results-dir",
        type=str,
        default=None,
        help="Use existing results dir (implies --skip-benchmark)",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    config_path = args.config

    # Step 1: Smoke test
    if not args.skip_smoke and not args.results_dir:
        logger.info("=" * 60)
        logger.info("Step 1: Smoke Test")
        logger.info("=" * 60)
        from research.tr123.smoke_test import run_smoke_test

        if not run_smoke_test(config_path):
            logger.error("Smoke test failed. Aborting.")
            sys.exit(1)

    # Step 2: Run benchmark
    if args.results_dir:
        results_dir = Path(args.results_dir)
        logger.info(f"Using existing results: {results_dir}")
    elif args.skip_benchmark:
        # Find latest results
        results_base = TR123_DIR / "results"
        if results_base.exists():
            subdirs = sorted(results_base.iterdir(), reverse=True)
            results_dir = subdirs[0] if subdirs else None
        else:
            results_dir = None
        if results_dir is None:
            logger.error("No existing results found. Run without --skip-benchmark.")
            sys.exit(1)
        logger.info(f"Using latest results: {results_dir}")
    else:
        logger.info("=" * 60)
        logger.info("Step 2: Running Benchmark")
        logger.info("=" * 60)
        from research.tr123.run_benchmark import run_matrix

        results_dir = run_matrix(config_path)

    # Step 3: Validate
    logger.info("=" * 60)
    logger.info("Step 3: Validating Results")
    logger.info("=" * 60)
    from research.tr123.validate import validate

    jsonl_path = results_dir / "raw_measurements.jsonl"
    if jsonl_path.exists():
        all_pass, issues = validate(jsonl_path, config_path)
        if not all_pass:
            logger.warning(f"Validation found {len(issues)} issues (continuing anyway)")
    else:
        logger.warning("No raw_measurements.jsonl found, skipping validation")

    # Step 4: KV-cache memory analysis
    logger.info("=" * 60)
    logger.info("Step 4: KV-Cache Memory Analysis")
    logger.info("=" * 60)
    from research.tr123.kv_cache_analysis import main as kv_main

    kv_results_dir = results_dir / "kv_cache_analysis"
    kv_main(config_path, kv_results_dir)

    # Step 5: Cost analysis
    logger.info("=" * 60)
    logger.info("Step 5: Cost Analysis")
    logger.info("=" * 60)
    from research.tr123.analyze_results import main as analyze_main

    if jsonl_path.exists():
        analyze_main(results_dir, config_path)
    else:
        logger.warning("Skipping cost analysis (no JSONL)")

    # Step 6: Cross-reference with TR119
    logger.info("=" * 60)
    logger.info("Step 6: Cross-Reference with TR119")
    logger.info("=" * 60)
    from research.tr123.cross_reference_tr119 import main as xref_main

    try:
        xref_main(results_dir)
    except Exception as e:
        logger.warning(f"TR119 cross-reference failed (non-fatal): {e}")

    # Step 7: Visualize
    logger.info("=" * 60)
    logger.info("Step 7: Generating Plots")
    logger.info("=" * 60)
    try:
        from research.tr123.visualize import generate_all_plots

        generate_all_plots(results_dir)
    except Exception as e:
        logger.warning(f"Visualization failed (non-fatal): {e}")

    # Step 8: Generate report
    logger.info("=" * 60)
    logger.info("Step 8: Generating Report")
    logger.info("=" * 60)
    from research.tr123.generate_report import generate_report

    report_path = generate_report(results_dir)

    # Summary
    logger.info("=" * 60)
    logger.info("TR123 Pipeline Complete")
    logger.info("=" * 60)
    logger.info(f"  Results: {results_dir}")
    logger.info(f"  Report:  {report_path}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
