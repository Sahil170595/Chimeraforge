# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 59.23s
- Sequential Estimate: 118.12s
- Speedup: 1.99x
- Efficiency: 99.7% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.18 tok/s
- TTFT: 774.89 ms
- Total Duration: 58855.43 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.40 tok/s
- TTFT: 815.22 ms
- Total Duration: 59197.72 ms

## Delta (B - A)
- Throughput Δ: +0.22 tok/s
- TTFT Δ: -40.33 ms (positive = Agent B faster TTFT)
