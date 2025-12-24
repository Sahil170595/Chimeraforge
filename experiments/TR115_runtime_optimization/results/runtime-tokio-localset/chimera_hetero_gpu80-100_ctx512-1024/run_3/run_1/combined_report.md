# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 12.98s
- Sequential Estimate: 23.40s
- Speedup: 1.80x
- Efficiency: 90.2% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.71 tok/s
- TTFT: 690.33 ms
- Total Duration: 10426.16 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 55.18 tok/s
- TTFT: 597.94 ms
- Total Duration: 12978.19 ms

## Delta (B - A)
- Throughput Δ: +14.47 tok/s
- TTFT Δ: +92.39 ms (positive = Agent B faster TTFT)
