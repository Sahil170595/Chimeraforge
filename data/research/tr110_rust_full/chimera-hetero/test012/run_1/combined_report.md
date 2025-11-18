# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 54.13s
- Sequential Estimate: 106.38s
- Speedup: 1.97x
- Efficiency: 98.3% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=120, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.53 tok/s
- TTFT: 603.45 ms
- Total Duration: 52222.17 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=140, num_ctx=2048, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 43.67 tok/s
- TTFT: 821.25 ms
- Total Duration: 54095.82 ms

## Delta (B - A)
- Throughput Δ: +2.14 tok/s
- TTFT Δ: -217.79 ms (positive = Agent B faster TTFT)
