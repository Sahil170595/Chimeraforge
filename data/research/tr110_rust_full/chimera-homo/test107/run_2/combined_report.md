# Rust Multi-Agent Report - Run 2

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 56.57s
- Sequential Estimate: 111.36s
- Speedup: 1.97x
- Efficiency: 98.4% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 43.23 tok/s
- TTFT: 657.42 ms
- Total Duration: 56538.21 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=2048, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.00 tok/s
- TTFT: 655.28 ms
- Total Duration: 54764.21 ms

## Delta (B - A)
- Throughput Δ: -2.23 tok/s
- TTFT Δ: +2.14 ms (positive = Agent B faster TTFT)
