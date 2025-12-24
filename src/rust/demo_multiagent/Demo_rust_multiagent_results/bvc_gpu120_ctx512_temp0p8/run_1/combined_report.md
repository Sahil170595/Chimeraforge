# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 15.34s
- Sequential Estimate: 20.12s
- Speedup: 1.31x
- Efficiency: 65.6% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 99.13 tok/s
- TTFT: 212.53 ms
- Total Duration: 4774.59 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11434
- Config: num_gpu=120, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 98.18 tok/s
- TTFT: 8559.70 ms
- Total Duration: 15340.65 ms

## Delta (B - A)
- Throughput Δ: -0.95 tok/s
- TTFT Δ: -8347.17 ms (positive = Agent B faster TTFT)
