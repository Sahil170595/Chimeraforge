# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 18.57s
- Sequential Estimate: 34.61s
- Speedup: 1.86x
- Efficiency: 93.2% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 44.91 tok/s
- TTFT: 6846.58 ms
- Total Duration: 16035.74 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 59.48 tok/s
- TTFT: 7142.12 ms
- Total Duration: 18569.42 ms

## Delta (B - A)
- Throughput Δ: +14.58 tok/s
- TTFT Δ: -295.53 ms (positive = Agent B faster TTFT)
