# Rust Multi-Agent Report - Run 3

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 10.06s
- Sequential Estimate: 16.32s
- Speedup: 1.62x
- Efficiency: 81.1% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.63 tok/s
- TTFT: 6283.39 ms
- Total Duration: 10064.82 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.56 tok/s
- TTFT: 194.11 ms
- Total Duration: 6255.57 ms

## Delta (B - A)
- Throughput Δ: -0.07 tok/s
- TTFT Δ: +6089.28 ms (positive = Agent B faster TTFT)
