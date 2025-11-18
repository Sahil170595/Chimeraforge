# Rust Multi-Agent Report - Run 3

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 56.76s
- Sequential Estimate: 112.20s
- Speedup: 1.98x
- Efficiency: 98.8% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.41 tok/s
- TTFT: 682.93 ms
- Total Duration: 56717.76 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.86 tok/s
- TTFT: 680.62 ms
- Total Duration: 55407.60 ms

## Delta (B - A)
- Throughput Δ: -1.54 tok/s
- TTFT Δ: +2.31 ms (positive = Agent B faster TTFT)
