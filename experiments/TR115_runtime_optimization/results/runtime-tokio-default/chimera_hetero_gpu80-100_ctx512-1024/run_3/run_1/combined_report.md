# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 14.19s
- Sequential Estimate: 26.25s
- Speedup: 1.85x
- Efficiency: 92.5% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.39 tok/s
- TTFT: 734.88 ms
- Total Duration: 12061.82 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 51.34 tok/s
- TTFT: 603.74 ms
- Total Duration: 14191.63 ms

## Delta (B - A)
- Throughput Δ: +10.96 tok/s
- TTFT Δ: +131.14 ms (positive = Agent B faster TTFT)
