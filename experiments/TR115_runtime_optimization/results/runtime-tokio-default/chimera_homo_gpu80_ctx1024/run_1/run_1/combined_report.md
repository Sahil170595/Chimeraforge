# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 14.36s
- Sequential Estimate: 27.09s
- Speedup: 1.89x
- Efficiency: 94.3% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.02 tok/s
- TTFT: 765.84 ms
- Total Duration: 12728.69 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 49.57 tok/s
- TTFT: 615.29 ms
- Total Duration: 14358.59 ms

## Delta (B - A)
- Throughput Δ: +8.55 tok/s
- TTFT Δ: +150.55 ms (positive = Agent B faster TTFT)
