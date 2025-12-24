# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 13.52s
- Sequential Estimate: 25.18s
- Speedup: 1.86x
- Efficiency: 93.2% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.13 tok/s
- TTFT: 682.58 ms
- Total Duration: 11669.54 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 50.94 tok/s
- TTFT: 611.53 ms
- Total Duration: 13515.12 ms

## Delta (B - A)
- Throughput Δ: +9.81 tok/s
- TTFT Δ: +71.05 ms (positive = Agent B faster TTFT)
