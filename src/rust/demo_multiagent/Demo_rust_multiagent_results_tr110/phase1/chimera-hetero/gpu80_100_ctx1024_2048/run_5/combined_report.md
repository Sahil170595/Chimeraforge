# Rust Multi-Agent Report - Run 5

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 8.33s
- Sequential Estimate: 9.32s
- Speedup: 1.12x
- Efficiency: 55.9% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 99.70 tok/s
- TTFT: 4118.62 ms
- Total Duration: 8329.92 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=100, num_ctx=2048, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 105.19 tok/s
- TTFT: 208.99 ms
- Total Duration: 991.04 ms

## Delta (B - A)
- Throughput Δ: +5.48 tok/s
- TTFT Δ: +3909.63 ms (positive = Agent B faster TTFT)
