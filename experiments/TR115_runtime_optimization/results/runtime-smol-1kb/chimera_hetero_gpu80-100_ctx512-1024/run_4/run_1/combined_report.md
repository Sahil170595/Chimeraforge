# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 12.30s
- Sequential Estimate: 21.49s
- Speedup: 1.75x
- Efficiency: 87.4% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 43.12 tok/s
- TTFT: 859.65 ms
- Total Duration: 9190.17 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 63.10 tok/s
- TTFT: 738.56 ms
- Total Duration: 12296.83 ms

## Delta (B - A)
- Throughput Δ: +19.98 tok/s
- TTFT Δ: +121.09 ms (positive = Agent B faster TTFT)
