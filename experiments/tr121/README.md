# TR121: Model Scaling Study

**Status:** Archived planning README  
**Depends On:** TR117, TR118, TR120

## Research Question

How do inference latency, throughput, and cold-start risk change as model size increases, and how does that differ for prefill vs KV-cached decode?

## Repository Layout

- `scripts/tr121/configs/` - scaling and ablation configs
- `scripts/tr121/run_scaling.py` - benchmark runner
- `scripts/tr121/analyze_scaling.py` - aggregation and scaling-law fitting
- `scripts/tr121/generate_report.py` - report scaffold generator
- `scripts/tr121/results/<RUN_ID>/` - run artifacts

## Canonical Report

- `outputs/publish_ready/reports/historical/Technical_Report_121v1.md`

## Note

This README is retained as an archived planning note. Use the publish-ready report above for the final write-up.
