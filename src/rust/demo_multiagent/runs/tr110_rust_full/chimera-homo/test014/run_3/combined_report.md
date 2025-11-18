# Rust Multi-Agent Report - Run 3

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 58.24s
- Sequential Estimate: 115.28s
- Speedup: 1.98x
- Efficiency: 99.0% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=60, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.99 tok/s
- TTFT: 661.28 ms
- Total Duration: 57016.25 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=60, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.45 tok/s
- TTFT: 651.46 ms
- Total Duration: 58203.19 ms

## Delta (B - A)
- Throughput Δ: +1.46 tok/s
- TTFT Δ: +9.82 ms (positive = Agent B faster TTFT)
