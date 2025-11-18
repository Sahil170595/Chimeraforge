# Rust Multi-Agent Report - Run 4

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 54.34s
- Sequential Estimate: 107.25s
- Speedup: 1.97x
- Efficiency: 98.7% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=0.6, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.88 tok/s
- TTFT: 650.42 ms
- Total Duration: 52877.32 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=2048, temp=0.6, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.81 tok/s
- TTFT: 656.31 ms
- Total Duration: 54308.47 ms

## Delta (B - A)
- Throughput Δ: +1.93 tok/s
- TTFT Δ: -5.89 ms (positive = Agent B faster TTFT)
