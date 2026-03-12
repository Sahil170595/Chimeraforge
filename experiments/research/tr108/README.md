# TR108: Single-Agent LLM Performance Analysis

**Status:** Complete
**Phase:** 1 (Foundation)

## Research Question

What are the baseline performance characteristics of LLM inference on consumer hardware (RTX 4080 laptop) using Ollama?

## Key Findings

- Established baseline latency/throughput for Ollama backends (Gemma3, Llama3)
- Characterized parameter tuning effects (temperature, top_p, top_k, context window)
- Foundation dataset for all subsequent TRs

## Contents

- `Technical_Report_108.md` — Full technical report
- `data/` — Raw benchmark data
  - `gemma3/` — Gemma3 model benchmarks
  - `llama3/` — Llama3 model benchmarks
  - `ollama/` — Ollama parameter tuning data
- `ollama_benchmark_summary.md` — Benchmark summary
- `baseline_*.txt` — Baseline performance reports

## Published Report

`PublishReady/reports/Technical_Report_108.md`

## Notebooks

`PublishReady/notebooks/TR108_Comprehensive.ipynb`
