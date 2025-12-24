# Rust Multi-Agent Report - Run 4

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 12.91s
- Sequential Estimate: 24.02s
- Speedup: 1.86x
- Efficiency: 93.0% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=512, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.04 tok/s
- TTFT: 296.14 ms
- Total Duration: 11110.08 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=512, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 50.50 tok/s
- TTFT: 300.09 ms
- Total Duration: 12912.66 ms

## Delta (B - A)
- Throughput Δ: +9.46 tok/s
- TTFT Δ: -3.96 ms (positive = Agent B faster TTFT)
