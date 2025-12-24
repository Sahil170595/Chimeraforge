# Rust Multi-Agent Report - Run 3

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 9.96s
- Sequential Estimate: 16.22s
- Speedup: 1.63x
- Efficiency: 81.4% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 101.39 tok/s
- TTFT: 6289.40 ms
- Total Duration: 9959.70 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 101.85 tok/s
- TTFT: 199.53 ms
- Total Duration: 6262.80 ms

## Delta (B - A)
- Throughput Δ: +0.46 tok/s
- TTFT Δ: +6089.87 ms (positive = Agent B faster TTFT)
