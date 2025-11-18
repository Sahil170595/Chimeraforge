# Rust Multi-Agent Report - Run 3

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 56.13s
- Sequential Estimate: 109.65s
- Speedup: 1.95x
- Efficiency: 97.7% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=60, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 44.44 tok/s
- TTFT: 679.08 ms
- Total Duration: 56095.04 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=2048, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.09 tok/s
- TTFT: 676.01 ms
- Total Duration: 53499.78 ms

## Delta (B - A)
- Throughput Δ: -3.34 tok/s
- TTFT Δ: +3.07 ms (positive = Agent B faster TTFT)
