# Rust Multi-Agent Report - Run 4

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 11.28s
- Sequential Estimate: 15.27s
- Speedup: 1.35x
- Efficiency: 67.7% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.62 tok/s
- TTFT: 206.19 ms
- Total Duration: 3994.66 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 99.49 tok/s
- TTFT: 4026.52 ms
- Total Duration: 11276.99 ms

## Delta (B - A)
- Throughput Δ: -1.13 tok/s
- TTFT Δ: -3820.34 ms (positive = Agent B faster TTFT)
