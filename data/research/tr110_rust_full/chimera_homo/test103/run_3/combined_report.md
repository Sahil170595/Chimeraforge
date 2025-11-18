# Rust Multi-Agent Report - Run 3

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 54.65s
- Sequential Estimate: 107.90s
- Speedup: 1.97x
- Efficiency: 98.7% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.6, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.06 tok/s
- TTFT: 655.44 ms
- Total Duration: 53220.14 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=0.6, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.59 tok/s
- TTFT: 547.20 ms
- Total Duration: 54610.59 ms

## Delta (B - A)
- Throughput Δ: +1.53 tok/s
- TTFT Δ: +108.24 ms (positive = Agent B faster TTFT)
