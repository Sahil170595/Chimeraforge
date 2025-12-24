# Rust Multi-Agent Report - Run 4

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 18.10s
- Sequential Estimate: 25.78s
- Speedup: 1.42x
- Efficiency: 71.2% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 98.73 tok/s
- TTFT: 3949.35 ms
- Total Duration: 7679.18 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11434
- Config: num_gpu=60, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 98.91 tok/s
- TTFT: 11426.05 ms
- Total Duration: 18099.53 ms

## Delta (B - A)
- Throughput Δ: +0.18 tok/s
- TTFT Δ: -7476.70 ms (positive = Agent B faster TTFT)
