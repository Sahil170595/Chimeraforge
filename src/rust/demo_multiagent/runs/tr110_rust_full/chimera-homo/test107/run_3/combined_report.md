# Rust Multi-Agent Report - Run 3

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 55.80s
- Sequential Estimate: 109.38s
- Speedup: 1.96x
- Efficiency: 98.0% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.94 tok/s
- TTFT: 644.86 ms
- Total Duration: 53554.51 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=2048, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 44.08 tok/s
- TTFT: 656.42 ms
- Total Duration: 55770.95 ms

## Delta (B - A)
- Throughput Δ: +3.13 tok/s
- TTFT Δ: -11.56 ms (positive = Agent B faster TTFT)
