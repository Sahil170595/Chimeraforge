#!/usr/bin/env python3
"""
Compare TR115 results directly to TR114 baseline

Loads TR114 tokio-default results and compares each TR115 runtime variant.
"""

import json
from pathlib import Path
import statistics

REPO_ROOT = Path(__file__).parent.parent.parent.parent
# TR114 results may be in outputs/runs or data/research
TR114_RESULTS = REPO_ROOT / "src" / "rust" / "demo_multiagent" / "Demo_rust_multiagent_results_tr110_dual"
if not TR114_RESULTS.exists():
    # Try alternative location
    TR114_RESULTS = REPO_ROOT / "outputs" / "runs" / "tr110_rust_full"
TR115_RESULTS = Path(__file__).parent.parent / "results"
ANALYSIS_DIR = Path(__file__).parent.parent / "analysis"


def load_tr114_baseline() -> dict:
    """Load TR114 baseline results."""
    if not TR114_RESULTS.exists():
        print(f"Warning: TR114 results not found at {TR114_RESULTS}")
        return None

    efficiencies = []

    # Scan TR114 results
    for phase_dir in TR114_RESULTS.iterdir():
        if not phase_dir.is_dir() or not phase_dir.name.startswith("phase"):
            continue

        for scenario_dir in phase_dir.iterdir():
            if not scenario_dir.is_dir():
                continue

            for config_dir in scenario_dir.iterdir():
                if not config_dir.is_dir():
                    continue

                # Check for summary.json
                summary_file = config_dir / "summary.json"
                if summary_file.exists():
                    try:
                        with open(summary_file) as f:
                            data = json.load(f)
                            if "efficiency_percent" in data:
                                efficiencies.append(data["efficiency_percent"])
                    except Exception:
                        pass

    if not efficiencies:
        return None

    return {
        "peak_efficiency": max(efficiencies),
        "mean_efficiency": statistics.mean(efficiencies),
        "stddev_efficiency": statistics.stdev(efficiencies)
        if len(efficiencies) > 1
        else 0,
        "count": len(efficiencies),
    }


def load_tr115_runtime(runtime: str) -> dict:
    """Load results for a TR115 runtime variant."""
    runtime_dir = TR115_RESULTS / runtime
    if not runtime_dir.exists():
        return None

    efficiencies = []

    for config_dir in runtime_dir.iterdir():
        if not config_dir.is_dir():
            continue

        for run_dir in config_dir.iterdir():
            if not run_dir.is_dir() or not run_dir.name.startswith("run_"):
                continue

            metrics_file = run_dir / "metrics.json"
            if metrics_file.exists():
                try:
                    with open(metrics_file) as f:
                        data = json.load(f)
                        # Handle nested summary
                        if "summary" in data:
                            data = data["summary"]
                        if "efficiency_percent" in data:
                            efficiencies.append(data["efficiency_percent"])
                except Exception:
                    pass

    if not efficiencies:
        return None

    return {
        "runtime": runtime,
        "peak_efficiency": max(efficiencies),
        "mean_efficiency": statistics.mean(efficiencies),
        "stddev_efficiency": statistics.stdev(efficiencies)
        if len(efficiencies) > 1
        else 0,
        "count": len(efficiencies),
    }


def main():
    print("=" * 80)
    print("TR115 vs TR114 Direct Comparison")
    print("=" * 80)

    # Load TR114 baseline
    print("\nLoading TR114 baseline...")
    tr114 = load_tr114_baseline()
    if not tr114:
        print("Could not load TR114 baseline results")
        return 1

    print("TR114 (tokio-default):")
    print(f"  Peak: {tr114['peak_efficiency']:.1f}%")
    print(
        f"  Mean: {tr114['mean_efficiency']:.1f}% ± {tr114['stddev_efficiency']:.1f}pp"
    )
    print(f"  Samples: {tr114['count']}")

    # Load TR115 variants
    print("\nLoading TR115 variants...")
    tr115_runtimes = []
    for runtime in [
        "runtime-tokio-localset",
        "runtime-async-std",
        "runtime-smol",
        "runtime-smol-1kb",
    ]:
        result = load_tr115_runtime(runtime)
        if result:
            tr115_runtimes.append(result)
            print(f"\n{runtime.replace('runtime-', '')}:")
            print(f"  Peak: {result['peak_efficiency']:.1f}%")
            print(
                f"  Delta: +{result['peak_efficiency'] - tr114['peak_efficiency']:.1f}pp"
            )

    if not tr115_runtimes:
        print("\nNo TR115 results found!")
        return 1

    # Generate comparison report
    lines = [
        "# TR115 vs TR114 Comparison",
        "",
        "## Baseline (TR114)",
        "",
        "**Runtime**: tokio-default",
        f"**Peak Efficiency**: {tr114['peak_efficiency']:.1f}%",
        f"**Mean Efficiency**: {tr114['mean_efficiency']:.1f}% ± {tr114['stddev_efficiency']:.1f}pp",
        "",
        "## TR115 Runtime Variants",
        "",
        "| Runtime | Peak Eff | Delta vs TR114 | Mean Eff | StdDev |",
        "|---------|----------|----------------|----------|--------|",
    ]

    for result in sorted(
        tr115_runtimes, key=lambda x: x["peak_efficiency"], reverse=True
    ):
        runtime_name = result["runtime"].replace("runtime-", "")
        delta = result["peak_efficiency"] - tr114["peak_efficiency"]
        lines.append(
            f"| {runtime_name} | "
            f"{result['peak_efficiency']:.1f}% | "
            f"+{delta:.1f}pp | "
            f"{result['mean_efficiency']:.1f}% | "
            f"{result['stddev_efficiency']:.1f}pp |"
        )

    lines.extend(
        [
            "",
            "## Key Findings",
            "",
        ]
    )

    # Find best
    best = max(tr115_runtimes, key=lambda x: x["peak_efficiency"])
    improvement = best["peak_efficiency"] - tr114["peak_efficiency"]

    lines.extend(
        [
            f"- **Best runtime**: {best['runtime'].replace('runtime-', '')}",
            f"- **Peak efficiency**: {best['peak_efficiency']:.1f}%",
            f"- **Improvement**: +{improvement:.1f}pp vs TR114 baseline",
            f"- **Hypothesis validated**: {'YES' if improvement > 2.0 else 'PARTIAL' if improvement > 1.0 else 'NO'}",
            "",
        ]
    )

    report_md = "\n".join(lines)

    # Save report
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    report_file = ANALYSIS_DIR / "tr114_comparison.md"
    with open(report_file, "w") as f:
        f.write(report_md)

    print(f"\n✓ Comparison report: {report_file}")
    print("\n" + "=" * 80)
    print("VERDICT")
    print("=" * 80)
    print(f"Best runtime: {best['runtime'].replace('runtime-', '')}")
    print(f"Improvement: +{improvement:.1f}pp")
    print(
        f"Hypothesis: {'✓ VALIDATED' if improvement > 2.0 else '~ PARTIAL' if improvement > 1.0 else '✗ NOT MET'}"
    )
    print("=" * 80)

    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
