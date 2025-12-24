# Rust Multi-Agent Report - Run 5

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 10.48s
- Sequential Estimate: 17.12s
- Speedup: 1.63x
- Efficiency: 81.7% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.75 tok/s
- TTFT: 6672.20 ms
- Total Duration: 10478.21 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 99.97 tok/s
- TTFT: 237.15 ms
- Total Duration: 6643.03 ms

## Delta (B - A)
- Throughput Δ: -0.78 tok/s
- TTFT Δ: +6435.05 ms (positive = Agent B faster TTFT)
