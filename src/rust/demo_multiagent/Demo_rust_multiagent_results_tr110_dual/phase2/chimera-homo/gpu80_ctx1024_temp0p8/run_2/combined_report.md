# Rust Multi-Agent Report - Run 2

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 11.80s
- Sequential Estimate: 21.20s
- Speedup: 1.80x
- Efficiency: 89.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 40.83 tok/s
- TTFT: 303.17 ms
- Total Duration: 9406.52 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 54.99 tok/s
- TTFT: 285.67 ms
- Total Duration: 11798.29 ms

## Delta (B - A)
- Throughput Δ: +14.16 tok/s
- TTFT Δ: +17.50 ms (positive = Agent B faster TTFT)
