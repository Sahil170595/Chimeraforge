# Rust Multi-Agent Report - Run 5

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 10.66s
- Sequential Estimate: 14.32s
- Speedup: 1.34x
- Efficiency: 67.1% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 101.45 tok/s
- TTFT: 200.96 ms
- Total Duration: 3653.22 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 99.87 tok/s
- TTFT: 3684.70 ms
- Total Duration: 10663.59 ms

## Delta (B - A)
- Throughput Δ: -1.58 tok/s
- TTFT Δ: -3483.74 ms (positive = Agent B faster TTFT)
