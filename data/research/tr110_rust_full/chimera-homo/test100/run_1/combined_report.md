# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 60.03s
- Sequential Estimate: 117.48s
- Speedup: 1.96x
- Efficiency: 97.8% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.6, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.23 tok/s
- TTFT: 3513.89 ms
- Total Duration: 57414.86 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=0.6, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 44.85 tok/s
- TTFT: 3566.92 ms
- Total Duration: 59994.15 ms

## Delta (B - A)
- Throughput Δ: +3.62 tok/s
- TTFT Δ: -53.03 ms (positive = Agent B faster TTFT)
