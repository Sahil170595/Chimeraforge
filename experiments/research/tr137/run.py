"""TR137: Run unified safety tax synthesis.

Usage:
    python research/tr137/run.py [-v] [--tr134-dir PATH] [--tr135-dir PATH]
      [--tr136-dir PATH] [--skip-analyze] [--skip-report] [--validate-only]

Steps:
  0. Validate source data availability (optional: --validate-only)
  1. Run analysis (18-pass synthesis of TR134+TR135+TR136)
  2. Generate report (21 sections)
  3. Write CSV outputs (deployment matrix, effect ranking)

No experiments to run — TR137 is pure synthesis.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

_DIR = Path(__file__).resolve().parent
_REPO = _DIR.parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from research.tr137.analyze import (
    analyze,
    print_summary,
    write_deployment_csv,
    write_effect_ranking_csv,
)
from research.tr137.generate_report import generate_report
from research.tr137.shared.env_fingerprint import capture_environment
from research.tr137.shared.utils import check_source_completeness, load_config

logger = logging.getLogger("tr137.run")


def main() -> int:
    parser = argparse.ArgumentParser(description="TR137 safety tax synthesis")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--tr134-dir", type=Path, default=None)
    parser.add_argument("--tr135-dir", type=Path, default=None)
    parser.add_argument("--tr136-dir", type=Path, default=None)
    parser.add_argument(
        "--skip-analyze", action="store_true", help="Skip analysis, use latest results"
    )
    parser.add_argument(
        "--skip-report", action="store_true", help="Skip report generation"
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only check source availability, then exit",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Load config
    config = load_config()
    if config:
        logger.info("Loaded config: %s", config.get("experiment", "tr137"))

    # Capture environment
    env = capture_environment()
    logger.info(
        "Platform: %s | Python: %s | Ollama: %s",
        env.get("platform", "?"),
        env.get("python_version", "?").split()[0],
        "available" if env.get("ollama_available") else "unavailable",
    )

    # Step 0: Validate sources
    print("=== Step 0: Checking source data availability ===")
    status = check_source_completeness()
    n_available = sum(1 for s in status.values() if s.get("available"))
    for label, info in sorted(status.items()):
        if info.get("available"):
            print(
                f"  {label.upper()}: available ({info.get('total_records', 0):,} records)"
            )
        else:
            print(f"  {label.upper()}: MISSING — {info.get('reason', 'unknown')}")

    if n_available == 0:
        print("\nERROR: No source data available — cannot run synthesis")
        return 1

    print(f"\n  {n_available}/3 sources available")
    if n_available < 3:
        print("  WARNING: Partial synthesis — some report sections will be incomplete")

    if args.validate_only:
        print("\n--validate-only: exiting after source check")
        return 0

    # Step 1: Analyze
    if not args.skip_analyze:
        print("\n=== Step 1: Running 18-pass synthesis analysis ===")
        analysis = analyze(args.tr134_dir, args.tr135_dir, args.tr136_dir)
        if not analysis:
            print("ERROR: Analysis failed — no source data loaded")
            return 1

        ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        run_dir = _REPO / "research" / "tr137" / "results" / ts
        run_dir.mkdir(parents=True, exist_ok=True)

        analysis_path = run_dir / "tr137_analysis.json"
        with open(analysis_path, "w", encoding="utf-8") as f:
            json.dump(analysis, f, indent=2, default=str)
        logger.info("Wrote analysis to %s", analysis_path)

        # Write CSVs
        write_deployment_csv(
            analysis.get("deployment_matrix", []),
            run_dir / "tr137_deployment_matrix.csv",
        )
        write_effect_ranking_csv(
            analysis.get("effect_sizes", {}), run_dir / "tr137_effect_ranking.csv"
        )
    else:
        print("\n=== Step 1: Skipping analysis (--skip-analyze) ===")
        from research.tr125.shared.utils import find_latest_run

        run_dir = find_latest_run(_REPO / "research" / "tr137" / "results")
        if run_dir is None:
            print("ERROR: No existing results to skip to")
            return 1
        analysis_path = run_dir / "tr137_analysis.json"
        if not analysis_path.exists():
            print(f"ERROR: Analysis file not found: {analysis_path}")
            return 1
        with open(analysis_path, encoding="utf-8") as f:
            analysis = json.load(f)
        print(f"  Using existing results from {run_dir.name}")

    # Step 2: Generate report
    if not args.skip_report:
        print("\n=== Step 2: Generating 21-section report ===")
        report = generate_report(analysis)
        report_path = run_dir / "tr137_report.md"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)

        n_lines = len(report.splitlines())
        logger.info("Wrote report (%d lines) to %s", n_lines, report_path)
    else:
        print("\n=== Step 2: Skipping report (--skip-report) ===")
        n_lines = 0

    # Summary
    meta = analysis.get("metadata", {})
    n_warnings = len(meta.get("validation_warnings", []))
    print(
        f"\nDone: {meta.get('n_sources', 0)}/3 sources, "
        f"{meta.get('total_samples_across_trs', 0):,} total samples, "
        f"{n_lines} report lines" + (f", {n_warnings} warnings" if n_warnings else "")
    )
    print(f"Results: {run_dir}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
