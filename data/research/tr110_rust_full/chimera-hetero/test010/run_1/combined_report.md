# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 55.81s
- Sequential Estimate: 110.58s
- Speedup: 1.98x
- Efficiency: 99.1% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.75 tok/s
- TTFT: 597.65 ms
- Total Duration: 55796.55 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=2048, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.03 tok/s
- TTFT: 827.42 ms
- Total Duration: 54751.01 ms

## Delta (B - A)
- Throughput Δ: -1.72 tok/s
- TTFT Δ: -229.77 ms (positive = Agent B faster TTFT)
