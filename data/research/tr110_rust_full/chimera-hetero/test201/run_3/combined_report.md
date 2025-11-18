# Rust Multi-Agent Report - Run 3

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 55.37s
- Sequential Estimate: 110.64s
- Speedup: 2.00x
- Efficiency: 99.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.82 tok/s
- TTFT: 611.74 ms
- Total Duration: 55238.28 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.02 tok/s
- TTFT: 668.22 ms
- Total Duration: 55340.29 ms

## Delta (B - A)
- Throughput Δ: +0.20 tok/s
- TTFT Δ: -56.48 ms (positive = Agent B faster TTFT)
