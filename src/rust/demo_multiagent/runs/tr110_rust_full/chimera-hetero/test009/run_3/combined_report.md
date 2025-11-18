# Rust Multi-Agent Report - Run 3

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 56.10s
- Sequential Estimate: 110.05s
- Speedup: 1.96x
- Efficiency: 98.1% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 43.92 tok/s
- TTFT: 656.02 ms
- Total Duration: 56074.73 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.05 tok/s
- TTFT: 655.08 ms
- Total Duration: 53915.30 ms

## Delta (B - A)
- Throughput Δ: -2.87 tok/s
- TTFT Δ: +0.94 ms (positive = Agent B faster TTFT)
