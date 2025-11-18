# Rust Multi-Agent Report - Run 4

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 62.94s
- Sequential Estimate: 124.10s
- Speedup: 1.97x
- Efficiency: 98.6% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.08 tok/s
- TTFT: 667.39 ms
- Total Duration: 61125.97 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 43.08 tok/s
- TTFT: 666.11 ms
- Total Duration: 62912.10 ms

## Delta (B - A)
- Throughput Δ: +2.00 tok/s
- TTFT Δ: +1.28 ms (positive = Agent B faster TTFT)
