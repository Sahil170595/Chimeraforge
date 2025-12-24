# Rust Multi-Agent Report - Run 3

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 11.99s
- Sequential Estimate: 21.42s
- Speedup: 1.79x
- Efficiency: 89.3% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.19 tok/s
- TTFT: 323.71 ms
- Total Duration: 9433.75 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 56.02 tok/s
- TTFT: 297.34 ms
- Total Duration: 11987.50 ms

## Delta (B - A)
- Throughput Δ: +14.83 tok/s
- TTFT Δ: +26.37 ms (positive = Agent B faster TTFT)
