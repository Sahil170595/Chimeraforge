# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 58.48s
- Sequential Estimate: 115.36s
- Speedup: 1.97x
- Efficiency: 98.6% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.83 tok/s
- TTFT: 625.15 ms
- Total Duration: 58444.35 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.25 tok/s
- TTFT: 821.19 ms
- Total Duration: 56846.64 ms

## Delta (B - A)
- Throughput Δ: -1.58 tok/s
- TTFT Δ: -196.04 ms (positive = Agent B faster TTFT)
