# Rust Multi-Agent Report - Run 4

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 10.01s
- Sequential Estimate: 14.27s
- Speedup: 1.42x
- Efficiency: 71.2% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 102.30 tok/s
- TTFT: 206.04 ms
- Total Duration: 4255.02 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 102.17 tok/s
- TTFT: 4283.89 ms
- Total Duration: 10012.92 ms

## Delta (B - A)
- Throughput Δ: -0.12 tok/s
- TTFT Δ: -4077.85 ms (positive = Agent B faster TTFT)
