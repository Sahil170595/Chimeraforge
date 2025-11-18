# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 56.09s
- Sequential Estimate: 111.97s
- Speedup: 2.00x
- Efficiency: 99.8% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.15 tok/s
- TTFT: 1013.10 ms
- Total Duration: 55837.60 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.04 tok/s
- TTFT: 1015.98 ms
- Total Duration: 56058.02 ms

## Delta (B - A)
- Throughput Δ: -0.11 tok/s
- TTFT Δ: -2.89 ms (positive = Agent B faster TTFT)
