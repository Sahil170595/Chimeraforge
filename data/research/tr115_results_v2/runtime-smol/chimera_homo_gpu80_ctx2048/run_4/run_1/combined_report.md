# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 55.41s
- Sequential Estimate: 110.58s
- Speedup: 2.00x
- Efficiency: 99.8% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.63 tok/s
- TTFT: 653.80 ms
- Total Duration: 55388.31 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.14 tok/s
- TTFT: 809.61 ms
- Total Duration: 55161.09 ms

## Delta (B - A)
- Throughput Δ: -0.49 tok/s
- TTFT Δ: -155.81 ms (positive = Agent B faster TTFT)
