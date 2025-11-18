# Rust Multi-Agent Report - Run 4

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 55.00s
- Sequential Estimate: 109.26s
- Speedup: 1.99x
- Efficiency: 99.3% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=60, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.88 tok/s
- TTFT: 678.92 ms
- Total Duration: 54228.57 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.78 tok/s
- TTFT: 663.97 ms
- Total Duration: 54964.54 ms

## Delta (B - A)
- Throughput Δ: +0.90 tok/s
- TTFT Δ: +14.95 ms (positive = Agent B faster TTFT)
