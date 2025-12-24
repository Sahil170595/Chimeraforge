# Rust Multi-Agent Report - Run 4

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 12.31s
- Sequential Estimate: 21.49s
- Speedup: 1.75x
- Efficiency: 87.3% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.36 tok/s
- TTFT: 269.79 ms
- Total Duration: 9186.10 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 58.87 tok/s
- TTFT: 294.99 ms
- Total Duration: 12304.83 ms

## Delta (B - A)
- Throughput Δ: +17.51 tok/s
- TTFT Δ: -25.20 ms (positive = Agent B faster TTFT)
