# Rust Multi-Agent Report - Run 2

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 56.61s
- Sequential Estimate: 112.70s
- Speedup: 1.99x
- Efficiency: 99.5% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=120, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.18 tok/s
- TTFT: 660.78 ms
- Total Duration: 56017.75 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=140, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.66 tok/s
- TTFT: 655.51 ms
- Total Duration: 56543.01 ms

## Delta (B - A)
- Throughput Δ: +0.48 tok/s
- TTFT Δ: +5.27 ms (positive = Agent B faster TTFT)
