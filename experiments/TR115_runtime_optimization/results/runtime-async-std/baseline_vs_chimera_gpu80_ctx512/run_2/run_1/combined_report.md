# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 10.43s
- Sequential Estimate: 10.43s
- Speedup: 1.00x
- Efficiency: 50.0% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 122.73 tok/s
- TTFT: 915.71 ms
- Total Duration: 4235.89 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 121.45 tok/s
- TTFT: 610.01 ms
- Total Duration: 6194.53 ms

## Delta (B - A)
- Throughput Δ: -1.28 tok/s
- TTFT Δ: +305.70 ms (positive = Agent B faster TTFT)
