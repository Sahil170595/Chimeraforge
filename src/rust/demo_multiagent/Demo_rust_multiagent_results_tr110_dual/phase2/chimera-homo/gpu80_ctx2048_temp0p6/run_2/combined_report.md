# Rust Multi-Agent Report - Run 2

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 12.20s
- Sequential Estimate: 21.17s
- Speedup: 1.74x
- Efficiency: 86.8% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=2048, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 42.01 tok/s
- TTFT: 212.29 ms
- Total Duration: 8972.92 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=2048, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 59.65 tok/s
- TTFT: 340.59 ms
- Total Duration: 12197.86 ms

## Delta (B - A)
- Throughput Δ: +17.64 tok/s
- TTFT Δ: -128.30 ms (positive = Agent B faster TTFT)
