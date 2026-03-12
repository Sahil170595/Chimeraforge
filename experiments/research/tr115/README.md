# TR115: Rust Runtime Optimization (v2)

**Status:** Complete
**Phase:** 1 (Foundation)
**Depends On:** TR109, TR114

## Research Question

Which Rust async runtime (Tokio, Smol, async-std) delivers optimal LLM inference throughput?

## Key Findings

- 5 runtime variants tested: tokio-default, tokio-localset, smol, smol-1kb, async-std
- Runtime choice significantly impacts multi-agent throughput
- Near-zero prior art on Rust async runtimes for LLM workloads

## Contents

- `runtime_optimization/` — Original experiment directory
  - `scripts/` — Runner and analysis scripts
  - `results_v2/` — Full results (5 runtimes × multiple configs)
  - `analysis/` — Detailed analysis and runtime comparison
  - `docs/` — TR115 plan and status
  - `aggregate_all.py` — Cross-runtime aggregation
- `data/` — Additional result data
- `configs/` — Experiment configurations

## Published Report

`PublishReady/reports/Technical_Report_115_v2.md`
