# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 13.09s
- Sequential Estimate: 24.66s
- Speedup: 1.88x
- Efficiency: 94.2% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.13 tok/s
- TTFT: 675.75 ms
- Total Duration: 11572.94 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 49.41 tok/s
- TTFT: 607.09 ms
- Total Duration: 13085.69 ms

## Delta (B - A)
- Throughput Δ: +8.28 tok/s
- TTFT Δ: +68.65 ms (positive = Agent B faster TTFT)
