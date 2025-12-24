# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 13.74s
- Sequential Estimate: 25.14s
- Speedup: 1.83x
- Efficiency: 91.5% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.99 tok/s
- TTFT: 734.07 ms
- Total Duration: 11398.36 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 53.77 tok/s
- TTFT: 595.42 ms
- Total Duration: 13740.31 ms

## Delta (B - A)
- Throughput Δ: +12.77 tok/s
- TTFT Δ: +138.65 ms (positive = Agent B faster TTFT)
