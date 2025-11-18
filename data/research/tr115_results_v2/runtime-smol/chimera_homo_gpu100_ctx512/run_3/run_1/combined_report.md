# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 52.75s
- Sequential Estimate: 104.38s
- Speedup: 1.98x
- Efficiency: 98.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 44.24 tok/s
- TTFT: 788.96 ms
- Total Duration: 52706.63 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.72 tok/s
- TTFT: 808.02 ms
- Total Duration: 51594.83 ms

## Delta (B - A)
- Throughput Δ: -1.52 tok/s
- TTFT Δ: -19.07 ms (positive = Agent B faster TTFT)
