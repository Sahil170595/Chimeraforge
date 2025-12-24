# Rust Multi-Agent Report - Run 5

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 12.15s
- Sequential Estimate: 22.30s
- Speedup: 1.84x
- Efficiency: 91.8% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=2048, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.95 tok/s
- TTFT: 210.42 ms
- Total Duration: 10153.70 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=2048, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 52.48 tok/s
- TTFT: 351.06 ms
- Total Duration: 12147.14 ms

## Delta (B - A)
- Throughput Δ: +10.53 tok/s
- TTFT Δ: -140.64 ms (positive = Agent B faster TTFT)
