# Rust Multi-Agent Report - Run 5

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 54.09s
- Sequential Estimate: 105.61s
- Speedup: 1.95x
- Efficiency: 97.6% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=120, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 44.48 tok/s
- TTFT: 662.50 ms
- Total Duration: 54061.94 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=140, num_ctx=2048, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.99 tok/s
- TTFT: 575.56 ms
- Total Duration: 51490.76 ms

## Delta (B - A)
- Throughput Δ: -3.49 tok/s
- TTFT Δ: +86.94 ms (positive = Agent B faster TTFT)
