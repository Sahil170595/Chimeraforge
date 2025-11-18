# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 56.45s
- Sequential Estimate: 111.70s
- Speedup: 1.98x
- Efficiency: 98.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.87 tok/s
- TTFT: 794.42 ms
- Total Duration: 56420.11 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.13 tok/s
- TTFT: 735.14 ms
- Total Duration: 55221.79 ms

## Delta (B - A)
- Throughput Δ: -1.74 tok/s
- TTFT Δ: +59.28 ms (positive = Agent B faster TTFT)
