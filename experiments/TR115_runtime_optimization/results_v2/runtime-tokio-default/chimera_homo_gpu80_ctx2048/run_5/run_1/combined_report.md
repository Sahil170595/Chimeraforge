# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 55.82s
- Sequential Estimate: 109.78s
- Speedup: 1.97x
- Efficiency: 98.3% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 43.31 tok/s
- TTFT: 851.84 ms
- Total Duration: 55782.97 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.84 tok/s
- TTFT: 774.79 ms
- Total Duration: 53923.44 ms

## Delta (B - A)
- Throughput Δ: -2.47 tok/s
- TTFT Δ: +77.05 ms (positive = Agent B faster TTFT)
