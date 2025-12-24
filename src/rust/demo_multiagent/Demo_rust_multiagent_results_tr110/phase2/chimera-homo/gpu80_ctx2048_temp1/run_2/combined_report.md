# Rust Multi-Agent Report - Run 2

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 9.98s
- Sequential Estimate: 16.11s
- Speedup: 1.61x
- Efficiency: 80.7% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.81 tok/s
- TTFT: 6165.43 ms
- Total Duration: 9976.53 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 101.25 tok/s
- TTFT: 224.87 ms
- Total Duration: 6134.25 ms

## Delta (B - A)
- Throughput Δ: +0.43 tok/s
- TTFT Δ: +5940.56 ms (positive = Agent B faster TTFT)
