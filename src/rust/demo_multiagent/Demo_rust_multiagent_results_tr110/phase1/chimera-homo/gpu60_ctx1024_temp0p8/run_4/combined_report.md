# Rust Multi-Agent Report - Run 4

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 10.97s
- Sequential Estimate: 17.71s
- Speedup: 1.61x
- Efficiency: 80.7% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=60, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.39 tok/s
- TTFT: 6764.91 ms
- Total Duration: 10970.19 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=60, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.25 tok/s
- TTFT: 227.98 ms
- Total Duration: 6736.62 ms

## Delta (B - A)
- Throughput Δ: -0.13 tok/s
- TTFT Δ: +6536.94 ms (positive = Agent B faster TTFT)
