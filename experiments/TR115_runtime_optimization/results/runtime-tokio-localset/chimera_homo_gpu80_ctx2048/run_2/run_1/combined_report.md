# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 13.31s
- Sequential Estimate: 24.78s
- Speedup: 1.86x
- Efficiency: 93.1% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.35 tok/s
- TTFT: 678.52 ms
- Total Duration: 11472.80 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 53.45 tok/s
- TTFT: 573.44 ms
- Total Duration: 13311.86 ms

## Delta (B - A)
- Throughput Δ: +11.10 tok/s
- TTFT Δ: +105.08 ms (positive = Agent B faster TTFT)
