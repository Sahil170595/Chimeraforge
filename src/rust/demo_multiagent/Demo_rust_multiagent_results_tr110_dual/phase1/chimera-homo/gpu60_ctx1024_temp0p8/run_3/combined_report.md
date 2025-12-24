# Rust Multi-Agent Report - Run 3

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 12.35s
- Sequential Estimate: 22.22s
- Speedup: 1.80x
- Efficiency: 89.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=60, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.40 tok/s
- TTFT: 254.63 ms
- Total Duration: 9864.12 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=60, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 55.46 tok/s
- TTFT: 301.27 ms
- Total Duration: 12351.77 ms

## Delta (B - A)
- Throughput Δ: +14.06 tok/s
- TTFT Δ: -46.63 ms (positive = Agent B faster TTFT)
