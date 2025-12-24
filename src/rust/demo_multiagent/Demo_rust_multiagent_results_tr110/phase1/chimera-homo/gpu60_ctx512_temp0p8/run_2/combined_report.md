# Rust Multi-Agent Report - Run 2

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 10.10s
- Sequential Estimate: 16.08s
- Speedup: 1.59x
- Efficiency: 79.6% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=60, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.55 tok/s
- TTFT: 6004.54 ms
- Total Duration: 10103.98 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=60, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.52 tok/s
- TTFT: 231.58 ms
- Total Duration: 5975.14 ms

## Delta (B - A)
- Throughput Δ: -0.03 tok/s
- TTFT Δ: +5772.96 ms (positive = Agent B faster TTFT)
