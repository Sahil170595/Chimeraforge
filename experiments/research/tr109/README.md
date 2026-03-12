# TR109: Rust Single-Agent Performance Analysis

**Status:** Complete
**Phase:** 1 (Foundation)
**Depends On:** TR108

## Research Question

How does a Rust-based inference agent compare to Python for single-agent LLM workloads?

## Key Findings

- Rust agent achieves lower dispatch overhead vs Python
- Parameter sweep across temperature, context, GPU layers
- 5 full runs + rerun for statistical confidence

## Contents

- `Technical_Report_109.md` — Full technical report
- `rust_agent/` — Rust benchmark tool (Cargo project + sweep scripts)
  - `src/` — Rust source code
  - `run_tr109_sweep.ps1` — Sweep launcher
  - `Demo_rust_agent_tr109_run*/` — Individual run data
- `data/` — Consolidated benchmark data
  - `tr109_rust_full/` — Full parameter sweep results

## Published Report

`PublishReady/reports/Technical_Report_109.md`

## Notebooks

`PublishReady/notebooks/TR109_Comprehensive.ipynb`

## Note

The Rust agent tool (`rust_agent/`) is also used by TR111 and TR115.
