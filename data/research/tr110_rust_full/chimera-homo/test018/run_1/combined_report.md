# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 60.78s
- Sequential Estimate: 120.05s
- Speedup: 1.98x
- Efficiency: 98.8% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=120, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.34 tok/s
- TTFT: 599.53 ms
- Total Duration: 59239.47 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=120, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.86 tok/s
- TTFT: 827.24 ms
- Total Duration: 60741.24 ms

## Delta (B - A)
- Throughput Δ: +1.51 tok/s
- TTFT Δ: -227.70 ms (positive = Agent B faster TTFT)
