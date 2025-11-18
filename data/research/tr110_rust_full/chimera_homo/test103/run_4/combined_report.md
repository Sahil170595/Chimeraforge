# Rust Multi-Agent Report - Run 4

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 53.50s
- Sequential Estimate: 106.75s
- Speedup: 2.00x
- Efficiency: 99.8% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.6, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.89 tok/s
- TTFT: 660.12 ms
- Total Duration: 53226.99 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=0.6, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.96 tok/s
- TTFT: 525.95 ms
- Total Duration: 53464.40 ms

## Delta (B - A)
- Throughput Δ: +0.07 tok/s
- TTFT Δ: +134.17 ms (positive = Agent B faster TTFT)
