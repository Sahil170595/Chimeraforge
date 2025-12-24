# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 12.60s
- Sequential Estimate: 22.36s
- Speedup: 1.77x
- Efficiency: 88.7% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 39.04 tok/s
- TTFT: 777.72 ms
- Total Duration: 9763.46 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 56.53 tok/s
- TTFT: 604.85 ms
- Total Duration: 12601.10 ms

## Delta (B - A)
- Throughput Δ: +17.49 tok/s
- TTFT Δ: +172.87 ms (positive = Agent B faster TTFT)
