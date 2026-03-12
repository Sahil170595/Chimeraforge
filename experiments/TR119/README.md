# TR119: Cost & Energy Analysis

**Status:** Infrastructure complete; archived planning README  
**Depends On:** TR117, TR118

## Research Question

What is the true total cost of ownership (TCO) for each backend, including energy consumption and cloud pricing variability?

## Repository Layout

- `run_experiment.py` - End-to-end orchestrator (benchmark -> analyze -> statistical analysis -> visualize -> report)
- `run_benchmark.py` - Benchmark runner with resource telemetry
- `analyze_results.py` - Statistical analysis plus cost and energy calculations
- `statistical_analysis.py` - Hypothesis testing, effect sizes, and bootstrap confidence intervals
- `visualize.py` - Cost, energy, and throughput plots
- `generate_report.py` - Publish-ready report generator
- `configs/` - Baseline, smoke, and matrix configurations

## Canonical Report

- `outputs/publish_ready/reports/Technical_Report_119v1.md`

## Note

This README is retained as an archived planning note. Use the publish-ready report above for the final conclusions.
