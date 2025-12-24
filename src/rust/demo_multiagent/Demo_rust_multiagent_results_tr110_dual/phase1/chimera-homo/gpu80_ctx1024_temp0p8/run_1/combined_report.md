# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 12.96s
- Sequential Estimate: 23.50s
- Speedup: 1.81x
- Efficiency: 90.6% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.74 tok/s
- TTFT: 236.55 ms
- Total Duration: 10541.27 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 54.24 tok/s
- TTFT: 329.34 ms
- Total Duration: 12960.05 ms

## Delta (B - A)
- Throughput Δ: +12.49 tok/s
- TTFT Δ: -92.79 ms (positive = Agent B faster TTFT)
