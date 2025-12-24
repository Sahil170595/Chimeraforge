# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 17.12s
- Sequential Estimate: 24.70s
- Speedup: 1.44x
- Efficiency: 72.1% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 97.95 tok/s
- TTFT: 3568.00 ms
- Total Duration: 7583.03 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11434
- Config: num_gpu=120, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 98.15 tok/s
- TTFT: 11048.60 ms
- Total Duration: 17120.00 ms

## Delta (B - A)
- Throughput Δ: +0.20 tok/s
- TTFT Δ: -7480.60 ms (positive = Agent B faster TTFT)
