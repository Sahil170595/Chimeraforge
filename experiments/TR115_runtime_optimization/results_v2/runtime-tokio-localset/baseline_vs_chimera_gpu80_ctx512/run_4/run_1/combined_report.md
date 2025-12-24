# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 61.81s
- Sequential Estimate: 121.10s
- Speedup: 1.96x
- Efficiency: 98.0% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 43.51 tok/s
- TTFT: 1001.84 ms
- Total Duration: 61776.30 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.85 tok/s
- TTFT: 667.31 ms
- Total Duration: 59252.55 ms

## Delta (B - A)
- Throughput Δ: -2.66 tok/s
- TTFT Δ: +334.53 ms (positive = Agent B faster TTFT)
