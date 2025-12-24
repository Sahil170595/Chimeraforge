# Rust Multi-Agent Report - Run 4

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 12.47s
- Sequential Estimate: 22.35s
- Speedup: 1.79x
- Efficiency: 89.6% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.55 tok/s
- TTFT: 306.51 ms
- Total Duration: 9877.49 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 56.01 tok/s
- TTFT: 280.95 ms
- Total Duration: 12472.23 ms

## Delta (B - A)
- Throughput Δ: +14.46 tok/s
- TTFT Δ: +25.56 ms (positive = Agent B faster TTFT)
