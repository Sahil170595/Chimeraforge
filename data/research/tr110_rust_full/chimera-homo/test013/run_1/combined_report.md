# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 64.00s
- Sequential Estimate: 126.82s
- Speedup: 1.98x
- Efficiency: 99.1% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=60, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.49 tok/s
- TTFT: 3334.08 ms
- Total Duration: 63963.61 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=60, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.07 tok/s
- TTFT: 3431.26 ms
- Total Duration: 62778.55 ms

## Delta (B - A)
- Throughput Δ: -1.42 tok/s
- TTFT Δ: -97.18 ms (positive = Agent B faster TTFT)
