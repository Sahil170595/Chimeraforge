# Rust Multi-Agent Report - Run 4

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 16.73s
- Sequential Estimate: 23.89s
- Speedup: 1.43x
- Efficiency: 71.4% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=60, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 101.31 tok/s
- TTFT: 3345.83 ms
- Total Duration: 7161.14 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 100.29 tok/s
- TTFT: 10423.08 ms
- Total Duration: 16728.19 ms

## Delta (B - A)
- Throughput Δ: -1.02 tok/s
- TTFT Δ: -7077.25 ms (positive = Agent B faster TTFT)
