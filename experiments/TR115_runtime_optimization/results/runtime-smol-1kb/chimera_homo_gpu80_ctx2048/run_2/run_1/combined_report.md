# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 12.08s
- Sequential Estimate: 21.22s
- Speedup: 1.76x
- Efficiency: 87.8% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.93 tok/s
- TTFT: 895.42 ms
- Total Duration: 9131.91 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 62.15 tok/s
- TTFT: 683.59 ms
- Total Duration: 12083.87 ms

## Delta (B - A)
- Throughput Δ: +19.22 tok/s
- TTFT Δ: +211.83 ms (positive = Agent B faster TTFT)
