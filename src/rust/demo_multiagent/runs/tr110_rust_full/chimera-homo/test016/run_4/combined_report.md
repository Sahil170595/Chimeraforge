# Rust Multi-Agent Report - Run 4

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 57.14s
- Sequential Estimate: 113.66s
- Speedup: 1.99x
- Efficiency: 99.5% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.73 tok/s
- TTFT: 656.44 ms
- Total Duration: 57112.49 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.00 tok/s
- TTFT: 647.22 ms
- Total Duration: 56488.91 ms

## Delta (B - A)
- Throughput Δ: -0.73 tok/s
- TTFT Δ: +9.22 ms (positive = Agent B faster TTFT)
