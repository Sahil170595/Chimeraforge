# Rust Multi-Agent Report - Run 3

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 14.94s
- Sequential Estimate: 18.89s
- Speedup: 1.26x
- Efficiency: 63.2% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 100.48 tok/s
- TTFT: 204.11 ms
- Total Duration: 3948.14 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11434
- Config: num_gpu=60, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 99.31 tok/s
- TTFT: 8047.00 ms
- Total Duration: 14939.25 ms

## Delta (B - A)
- Throughput Δ: -1.17 tok/s
- TTFT Δ: -7842.89 ms (positive = Agent B faster TTFT)
