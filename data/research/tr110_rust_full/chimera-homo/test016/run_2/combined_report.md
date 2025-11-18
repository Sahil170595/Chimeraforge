# Rust Multi-Agent Report - Run 2

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 59.23s
- Sequential Estimate: 115.60s
- Speedup: 1.95x
- Efficiency: 97.6% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 44.18 tok/s
- TTFT: 647.23 ms
- Total Duration: 59201.82 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.06 tok/s
- TTFT: 653.72 ms
- Total Duration: 56344.60 ms

## Delta (B - A)
- Throughput Δ: -3.12 tok/s
- TTFT Δ: -6.49 ms (positive = Agent B faster TTFT)
