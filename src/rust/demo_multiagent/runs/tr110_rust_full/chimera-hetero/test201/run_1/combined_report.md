# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 61.71s
- Sequential Estimate: 121.56s
- Speedup: 1.97x
- Efficiency: 98.5% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.76 tok/s
- TTFT: 3241.82 ms
- Total Duration: 59818.57 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 43.20 tok/s
- TTFT: 3435.10 ms
- Total Duration: 61687.30 ms

## Delta (B - A)
- Throughput Δ: +2.43 tok/s
- TTFT Δ: -193.28 ms (positive = Agent B faster TTFT)
