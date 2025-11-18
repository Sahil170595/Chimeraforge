# Rust Multi-Agent Report - Run 4

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 56.99s
- Sequential Estimate: 113.39s
- Speedup: 1.99x
- Efficiency: 99.5% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=60, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.19 tok/s
- TTFT: 661.55 ms
- Total Duration: 56372.32 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=2048, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.89 tok/s
- TTFT: 663.09 ms
- Total Duration: 56955.73 ms

## Delta (B - A)
- Throughput Δ: +0.70 tok/s
- TTFT Δ: -1.53 ms (positive = Agent B faster TTFT)
