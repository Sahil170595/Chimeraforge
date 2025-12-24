# Rust Multi-Agent Report - Run 5

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 11.51s
- Sequential Estimate: 20.19s
- Speedup: 1.75x
- Efficiency: 87.7% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.15 tok/s
- TTFT: 308.70 ms
- Total Duration: 8686.60 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=1024, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 58.48 tok/s
- TTFT: 303.54 ms
- Total Duration: 11508.01 ms

## Delta (B - A)
- Throughput Δ: +17.32 tok/s
- TTFT Δ: +5.16 ms (positive = Agent B faster TTFT)
