# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 15.66s
- Sequential Estimate: 22.64s
- Speedup: 1.45x
- Efficiency: 72.3% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 97.26 tok/s
- TTFT: 10974.31 ms
- Total Duration: 15656.00 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11434
- Config: num_gpu=60, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 98.83 tok/s
- TTFT: 243.61 ms
- Total Duration: 6987.79 ms

## Delta (B - A)
- Throughput Δ: +1.58 tok/s
- TTFT Δ: +10730.71 ms (positive = Agent B faster TTFT)
