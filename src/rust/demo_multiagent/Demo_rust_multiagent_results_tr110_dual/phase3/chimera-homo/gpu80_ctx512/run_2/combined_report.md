# Rust Multi-Agent Report - Run 2

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 13.17s
- Sequential Estimate: 24.50s
- Speedup: 1.86x
- Efficiency: 93.0% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 40.97 tok/s
- TTFT: 292.36 ms
- Total Duration: 11329.32 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 50.60 tok/s
- TTFT: 307.42 ms
- Total Duration: 13170.50 ms

## Delta (B - A)
- Throughput Δ: +9.63 tok/s
- TTFT Δ: -15.06 ms (positive = Agent B faster TTFT)
