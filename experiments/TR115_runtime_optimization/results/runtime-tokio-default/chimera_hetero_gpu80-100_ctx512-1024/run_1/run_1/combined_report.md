# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 21.59s
- Sequential Estimate: 41.00s
- Speedup: 1.90x
- Efficiency: 94.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.10 tok/s
- TTFT: 8071.79 ms
- Total Duration: 19405.07 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 50.92 tok/s
- TTFT: 8078.66 ms
- Total Duration: 21589.98 ms

## Delta (B - A)
- Throughput Δ: +10.82 tok/s
- TTFT Δ: -6.86 ms (positive = Agent B faster TTFT)
