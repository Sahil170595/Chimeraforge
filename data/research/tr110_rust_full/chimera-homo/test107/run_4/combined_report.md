# Rust Multi-Agent Report - Run 4

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 56.31s
- Sequential Estimate: 111.73s
- Speedup: 1.98x
- Efficiency: 99.2% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.00 tok/s
- TTFT: 677.19 ms
- Total Duration: 55393.56 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=2048, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.09 tok/s
- TTFT: 659.47 ms
- Total Duration: 56276.71 ms

## Delta (B - A)
- Throughput Δ: +1.08 tok/s
- TTFT Δ: +17.72 ms (positive = Agent B faster TTFT)
