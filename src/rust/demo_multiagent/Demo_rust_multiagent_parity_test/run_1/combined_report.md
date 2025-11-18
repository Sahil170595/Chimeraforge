# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 56.67s
- Sequential Estimate: 109.11s
- Speedup: 1.93x
- Efficiency: 96.3% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 47.62 tok/s
- TTFT: 954.34 ms
- Total Duration: 52389.02 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: Ollama defaults
- Throughput: 46.50 tok/s
- TTFT: 2993.26 ms
- Total Duration: 56625.40 ms

## Delta (B - A)
- Throughput Δ: -1.12 tok/s
- TTFT Δ: -2038.92 ms (positive = Agent B faster TTFT)
