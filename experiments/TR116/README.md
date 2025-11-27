# TR116 (Cross-Model Benchmarks: Qwen 2.5 vs Gemma 3 vs Llama 3.1)

**Status:** ✅ Complete (Nov 26, 2025)  
**Report:** [Technical Report 116](../../outputs/publish_ready/reports/Technical_Report_116.md)

## Overview
TR116 executes the full Chimeraforge benchmark suite (single-agent and dual-Ollama multi-agent, Python and Rust) across three distinct model architectures to determine if model choice impacts multi-agent coordination efficiency.

## Models Tested
- **Gemma 3** (`gemma3:latest`): 4.3B params, Q4_K_M
- **Llama 3.1** (`llama3.1:8b-instruct-q4_0`): 8B params, Q4_0
- **Qwen 2.5** (`qwen2.5:7b`): 7B params, Q4_K_M

## Key Results Summary

| Metric | Gemma 3 (Rust) | Llama 3.1 (Rust) | Qwen 2.5 (Rust) | Verdict |
|--------|----------------|------------------|-----------------|---------|
| **Multi-Agent Efficiency** | **99.2%** 🏆 | 98.5% ✅ | 90.0% ⚠️ | Gemma scales best |
| **Speedup (vs Seq)** | 1.98x | 1.97x | 1.80x | Near-perfect for Gemma |
| **Throughput Delta** | Balanced | Balanced | +12.4 tok/s | Qwen has imbalance |

**Critical Findings:**
1. **Rust Dominance:** Rust achieves **+12-17pp higher efficiency** than Python across all models.
2. **Gemma 3 Champion:** Achieves 99.2% efficiency in Rust, making it the optimal choice for high-concurrency agent swarms.
3. **Qwen 2.5 Limitations:** Shows significant throughput imbalance (+12.4 tok/s delta) between agents, leading to scheduler starvation and lower efficiency (90%).
4. **Python Ceiling:** Python never exceeds 86% efficiency regardless of model, confirming structural limitations of the single-threaded event loop for this workload.

## Benchmark Matrix
- **Single-agent**: Python + Rust parity runs (GPU 80, CTX 1024, TEMP 0.8)
- **Multi-agent**: Dual Ollama (Ports 11434/11435), Scenarios: `baseline_vs_chimera`, `chimera_homo`
- **Total Runs:** 60+ multi-agent runs, 30+ single-agent runs

## Reproducibility
See [Technical Report 116](../../outputs/publish_ready/reports/Technical_Report_116.md) for full reproduction steps and detailed per-run analysis.
