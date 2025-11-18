# Rust Multi-Agent Report - Run 3

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 54.97s
- Sequential Estimate: 108.25s
- Speedup: 1.97x
- Efficiency: 98.5% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.94 tok/s
- TTFT: 654.70 ms
- Total Duration: 53264.59 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=2048, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 43.02 tok/s
- TTFT: 651.39 ms
- Total Duration: 54955.28 ms

## Delta (B - A)
- Throughput Δ: +2.08 tok/s
- TTFT Δ: +3.31 ms (positive = Agent B faster TTFT)
