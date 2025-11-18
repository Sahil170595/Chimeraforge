# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 58.24s
- Sequential Estimate: 115.11s
- Speedup: 1.98x
- Efficiency: 98.8% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 43.16 tok/s
- TTFT: 835.79 ms
- Total Duration: 58204.09 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.50 tok/s
- TTFT: 813.14 ms
- Total Duration: 56828.81 ms

## Delta (B - A)
- Throughput Δ: -1.67 tok/s
- TTFT Δ: +22.65 ms (positive = Agent B faster TTFT)
