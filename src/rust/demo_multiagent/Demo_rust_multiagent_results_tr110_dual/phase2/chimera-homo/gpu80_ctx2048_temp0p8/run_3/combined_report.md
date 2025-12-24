# Rust Multi-Agent Report - Run 3

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 12.59s
- Sequential Estimate: 23.31s
- Speedup: 1.85x
- Efficiency: 92.5% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=2048, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.64 tok/s
- TTFT: 213.64 ms
- Total Duration: 10714.36 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=2048, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 51.28 tok/s
- TTFT: 342.18 ms
- Total Duration: 12593.78 ms

## Delta (B - A)
- Throughput Δ: +9.64 tok/s
- TTFT Δ: -128.54 ms (positive = Agent B faster TTFT)
