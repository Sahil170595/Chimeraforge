# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 57.07s
- Sequential Estimate: 114.14s
- Speedup: 2.00x
- Efficiency: 100.0% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.28 tok/s
- TTFT: 609.46 ms
- Total Duration: 57035.34 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.02 tok/s
- TTFT: 826.85 ms
- Total Duration: 57031.61 ms

## Delta (B - A)
- Throughput Δ: -0.26 tok/s
- TTFT Δ: -217.39 ms (positive = Agent B faster TTFT)
