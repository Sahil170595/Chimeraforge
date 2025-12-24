# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 59.00s
- Sequential Estimate: 115.10s
- Speedup: 1.95x
- Efficiency: 97.5% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 44.57 tok/s
- TTFT: 1079.91 ms
- Total Duration: 58968.58 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.10 tok/s
- TTFT: 1057.40 ms
- Total Duration: 56067.29 ms

## Delta (B - A)
- Throughput Δ: -3.48 tok/s
- TTFT Δ: +22.51 ms (positive = Agent B faster TTFT)
