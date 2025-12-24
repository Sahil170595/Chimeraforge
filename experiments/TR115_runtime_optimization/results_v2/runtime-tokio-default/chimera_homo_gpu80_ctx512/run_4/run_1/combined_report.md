# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 54.26s
- Sequential Estimate: 107.10s
- Speedup: 1.97x
- Efficiency: 98.7% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 43.25 tok/s
- TTFT: 806.49 ms
- Total Duration: 54230.84 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.34 tok/s
- TTFT: 797.33 ms
- Total Duration: 52814.73 ms

## Delta (B - A)
- Throughput Δ: -1.90 tok/s
- TTFT Δ: +9.16 ms (positive = Agent B faster TTFT)
