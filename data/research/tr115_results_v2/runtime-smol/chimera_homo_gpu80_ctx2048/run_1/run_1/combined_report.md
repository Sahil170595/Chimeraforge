# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 53.95s
- Sequential Estimate: 106.16s
- Speedup: 1.97x
- Efficiency: 98.4% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.48 tok/s
- TTFT: 654.77 ms
- Total Duration: 52187.68 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 43.08 tok/s
- TTFT: 700.39 ms
- Total Duration: 53938.51 ms

## Delta (B - A)
- Throughput Δ: +1.60 tok/s
- TTFT Δ: -45.62 ms (positive = Agent B faster TTFT)
