# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 5.10s
- Sequential Estimate: 7.22s
- Speedup: 1.41x
- Efficiency: 70.7% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 90.20 tok/s
- TTFT: 695.97 ms
- Total Duration: 5104.77 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 45.54 tok/s
- TTFT: 602.71 ms
- Total Duration: 2111.94 ms

## Delta (B - A)
- Throughput Δ: -44.66 tok/s
- TTFT Δ: +93.26 ms (positive = Agent B faster TTFT)
