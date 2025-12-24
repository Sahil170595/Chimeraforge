# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 18.42s
- Sequential Estimate: 26.63s
- Speedup: 1.45x
- Efficiency: 72.3% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 96.78 tok/s
- TTFT: 3983.06 ms
- Total Duration: 8213.23 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11434
- Config: num_gpu=120, num_ctx=1024, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 98.87 tok/s
- TTFT: 11954.88 ms
- Total Duration: 18416.99 ms

## Delta (B - A)
- Throughput Δ: +2.09 tok/s
- TTFT Δ: -7971.82 ms (positive = Agent B faster TTFT)
