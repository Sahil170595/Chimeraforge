# Rust Multi-Agent Report - Run 4

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 13.00s
- Sequential Estimate: 24.46s
- Speedup: 1.88x
- Efficiency: 94.1% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 40.92 tok/s
- TTFT: 312.38 ms
- Total Duration: 11459.23 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 49.17 tok/s
- TTFT: 310.49 ms
- Total Duration: 12996.47 ms

## Delta (B - A)
- Throughput Δ: +8.25 tok/s
- TTFT Δ: +1.89 ms (positive = Agent B faster TTFT)
