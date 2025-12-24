# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 13.12s
- Sequential Estimate: 24.68s
- Speedup: 1.88x
- Efficiency: 94.0% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.22 tok/s
- TTFT: 709.43 ms
- Total Duration: 11557.80 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 49.93 tok/s
- TTFT: 605.57 ms
- Total Duration: 13123.51 ms

## Delta (B - A)
- Throughput Δ: +8.71 tok/s
- TTFT Δ: +103.86 ms (positive = Agent B faster TTFT)
