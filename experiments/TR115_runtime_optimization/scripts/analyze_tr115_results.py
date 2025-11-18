#!/usr/bin/env python3
"""
TR115 Results Analysis Script

Analyzes benchmarks from all 5 runtime variants and compares:
- Efficiency vs TR114 baseline (95.7%)
- Gap vs TR110 target (99.25%)
- Statistical significance
- Configuration sensitivity
"""

import json
from pathlib import Path
import statistics

import pandas as pd

RESULTS_BASE = Path(__file__).parent.parent / "results"
ANALYSIS_DIR = Path(__file__).parent.parent / "analysis"

# Baseline and target values
TR114_BASELINE = 95.7  # Peak efficiency from TR114
TR110_TARGET = 99.25  # Peak efficiency from TR110 (Python)

RUNTIMES = [
    "runtime-tokio-default",
    "runtime-tokio-localset",
    "runtime-async-std",
    "runtime-smol",
    "runtime-smol-1kb",
]


def load_metrics(results_dir: Path) -> dict:
    """Load metrics.json from a benchmark run."""
    metrics_file = results_dir / "run_1" / "metrics.json"
    if not metrics_file.exists():
        return None

    try:
        with open(metrics_file) as f:
            data = json.load(f)
            # Extract summary if nested
            if "summary" in data:
                return data["summary"]
            return data
    except Exception as e:
        print(f"Error loading {metrics_file}: {e}")
        return None


def analyze_runtime(runtime: str) -> dict:
    """Analyze all results for a single runtime."""
    runtime_dir = RESULTS_BASE / runtime
    if not runtime_dir.exists():
        print(f"Warning: {runtime} directory not found")
        return None

    results = []

    # Collect all metrics
    for config_dir in runtime_dir.iterdir():
        if not config_dir.is_dir():
            continue

        config_id = config_dir.name
        config_efficiencies = []
        config_speedups = []

        for run_dir in config_dir.iterdir():
            if not run_dir.is_dir() or not run_dir.name.startswith("run_"):
                continue

            metrics = load_metrics(run_dir)
            if metrics and "efficiency_percent" in metrics:
                config_efficiencies.append(metrics["efficiency_percent"])
                config_speedups.append(metrics.get("concurrency_speedup", 0))

        if config_efficiencies:
            results.append(
                {
                    "config_id": config_id,
                    "mean_efficiency": statistics.mean(config_efficiencies),
                    "stddev_efficiency": statistics.stdev(config_efficiencies)
                    if len(config_efficiencies) > 1
                    else 0,
                    "mean_speedup": statistics.mean(config_speedups),
                    "stddev_speedup": statistics.stdev(config_speedups)
                    if len(config_speedups) > 1
                    else 0,
                    "runs": len(config_efficiencies),
                }
            )

    if not results:
        return None

    # Calculate aggregate stats
    all_efficiencies = [r["mean_efficiency"] for r in results]
    all_speedups = [r["mean_speedup"] for r in results]

    return {
        "runtime": runtime,
        "peak_efficiency": max(all_efficiencies),
        "mean_efficiency": statistics.mean(all_efficiencies),
        "stddev_efficiency": statistics.stdev(all_efficiencies)
        if len(all_efficiencies) > 1
        else 0,
        "peak_speedup": max(all_speedups),
        "mean_speedup": statistics.mean(all_speedups),
        "gain_vs_tr114": max(all_efficiencies) - TR114_BASELINE,
        "gap_vs_tr110": TR110_TARGET - max(all_efficiencies),
        "configs_tested": len(results),
        "details": results,
    }


def generate_comparison_table(runtime_stats: list[dict]) -> str:
    """Generate markdown comparison table."""
    lines = [
        "# TR115 Runtime Comparison",
        "",
        "## Summary",
        "",
        "| Runtime | Peak Eff | Mean Eff | Gain vs TR114 | Gap vs TR110 | StdDev |",
        "|---------|----------|----------|---------------|--------------|--------|",
    ]

    for stats in runtime_stats:
        runtime_name = stats["runtime"].replace("runtime-", "")
        lines.append(
            f"| {runtime_name} | "
            f"{stats['peak_efficiency']:.1f}% | "
            f"{stats['mean_efficiency']:.1f}% | "
            f"+{stats['gain_vs_tr114']:.1f}pp | "
            f"-{stats['gap_vs_tr110']:.1f}pp | "
            f"{stats['stddev_efficiency']:.1f}pp |"
        )

    lines.extend(
        [
            "",
            "## Baseline References",
            "",
            f"- TR114 baseline (tokio-default): {TR114_BASELINE}%",
            f"- TR110 target (Python dual Ollama): {TR110_TARGET}%",
            "",
        ]
    )

    return "\n".join(lines)


def generate_detailed_analysis(runtime_stats: list[dict]) -> str:
    """Generate detailed analysis markdown."""
    lines = ["# TR115 Detailed Analysis", "", "## Per-Runtime Analysis", ""]

    for stats in runtime_stats:
        runtime_name = stats["runtime"].replace("runtime-", "")
        lines.extend(
            [
                f"### {runtime_name}",
                "",
                f"**Peak Efficiency**: {stats['peak_efficiency']:.1f}%",
                f"**Mean Efficiency**: {stats['mean_efficiency']:.1f}% ± {stats['stddev_efficiency']:.1f}pp",
                f"**Peak Speedup**: {stats['peak_speedup']:.2f}x",
                f"**Gain vs TR114**: +{stats['gain_vs_tr114']:.1f}pp",
                f"**Gap vs TR110**: -{stats['gap_vs_tr110']:.1f}pp",
                "",
                "**Top 3 Configurations**:",
                "",
            ]
        )

        # Sort configs by efficiency
        sorted_configs = sorted(
            stats["details"], key=lambda x: x["mean_efficiency"], reverse=True
        )[:3]
        for i, config in enumerate(sorted_configs, 1):
            lines.append(
                f"{i}. {config['config_id']}: "
                f"{config['mean_efficiency']:.1f}% ± {config['stddev_efficiency']:.1f}pp "
                f"({config['mean_speedup']:.2f}x speedup)"
            )

        lines.append("")

    return "\n".join(lines)


def main():
    print("=" * 80)
    print("TR115 Results Analysis")
    print("=" * 80)

    # Create analysis directory
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)

    # Analyze each runtime
    runtime_stats = []
    for runtime in RUNTIMES:
        print(f"\nAnalyzing {runtime}...")
        stats = analyze_runtime(runtime)
        if stats:
            runtime_stats.append(stats)
            print(f"  Peak efficiency: {stats['peak_efficiency']:.1f}%")
            print(f"  Gain vs TR114: +{stats['gain_vs_tr114']:.1f}pp")
            print(f"  Gap vs TR110: -{stats['gap_vs_tr110']:.1f}pp")

    if not runtime_stats:
        print("\nNo results found!")
        return 1

    # Generate comparison table
    comparison_md = generate_comparison_table(runtime_stats)
    comparison_file = ANALYSIS_DIR / "runtime_comparison.md"
    with open(comparison_file, "w") as f:
        f.write(comparison_md)
    print(f"\n[OK] Comparison table: {comparison_file}")

    # Generate detailed analysis
    detailed_md = generate_detailed_analysis(runtime_stats)
    detailed_file = ANALYSIS_DIR / "detailed_analysis.md"
    with open(detailed_file, "w") as f:
        f.write(detailed_md)
    print(f"[OK] Detailed analysis: {detailed_file}")

    # Save to CSV
    df = pd.DataFrame(
        [
            {
                "runtime": s["runtime"].replace("runtime-", ""),
                "peak_efficiency": s["peak_efficiency"],
                "mean_efficiency": s["mean_efficiency"],
                "stddev_efficiency": s["stddev_efficiency"],
                "peak_speedup": s["peak_speedup"],
                "gain_vs_tr114": s["gain_vs_tr114"],
                "gap_vs_tr110": s["gap_vs_tr110"],
            }
            for s in runtime_stats
        ]
    )
    csv_file = ANALYSIS_DIR / "runtime_comparison.csv"
    df.to_csv(csv_file, index=False)
    print(f"[OK] CSV export: {csv_file}")

    # Print summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    best = max(runtime_stats, key=lambda x: x["peak_efficiency"])
    print(f"Best runtime: {best['runtime'].replace('runtime-', '')}")
    print(f"Peak efficiency: {best['peak_efficiency']:.1f}%")
    print(f"Improvement: +{best['gain_vs_tr114']:.1f}pp vs TR114")
    print(f"Remaining gap: -{best['gap_vs_tr110']:.1f}pp vs TR110")
    print("=" * 80)

    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
