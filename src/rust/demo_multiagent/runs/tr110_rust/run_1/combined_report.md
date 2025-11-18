# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 70.70s
- Sequential Estimate: 141.10s
- Speedup: 2.00x
- Efficiency: 99.8% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 40.01 tok/s
- TTFT: 4509.20 ms
- Total Duration: 70648.10 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: Ollama defaults
- Throughput: 39.56 tok/s
- TTFT: 4705.01 ms
- Total Duration: 70340.21 ms

## Delta (B - A)
- Throughput Δ: -0.45 tok/s
- TTFT Δ: -195.81 ms (positive = Agent B faster TTFT)
