# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 20.12s
- Sequential Estimate: 37.21s
- Speedup: 1.85x
- Efficiency: 92.5% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.96 tok/s
- TTFT: 7717.95 ms
- Total Duration: 17086.71 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 58.37 tok/s
- TTFT: 7964.17 ms
- Total Duration: 20120.33 ms

## Delta (B - A)
- Throughput Δ: +15.41 tok/s
- TTFT Δ: -246.22 ms (positive = Agent B faster TTFT)
