# Rust Multi-Agent Report - Run 2

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 10.00s
- Sequential Estimate: 13.99s
- Speedup: 1.40x
- Efficiency: 69.9% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 102.20 tok/s
- TTFT: 204.41 ms
- Total Duration: 3982.71 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.70 tok/s
- TTFT: 4011.65 ms
- Total Duration: 10002.80 ms

## Delta (B - A)
- Throughput Δ: -1.50 tok/s
- TTFT Δ: -3807.24 ms (positive = Agent B faster TTFT)
