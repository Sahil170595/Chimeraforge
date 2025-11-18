# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 55.86s
- Sequential Estimate: 111.24s
- Speedup: 1.99x
- Efficiency: 99.6% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.49 tok/s
- TTFT: 659.66 ms
- Total Duration: 55354.01 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.81 tok/s
- TTFT: 842.63 ms
- Total Duration: 55832.87 ms

## Delta (B - A)
- Throughput Δ: +0.32 tok/s
- TTFT Δ: -182.97 ms (positive = Agent B faster TTFT)
