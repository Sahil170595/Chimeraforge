# Rust Multi-Agent Report - Run 4

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 55.06s
- Sequential Estimate: 108.96s
- Speedup: 1.98x
- Efficiency: 99.0% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.47 tok/s
- TTFT: 655.66 ms
- Total Duration: 55022.35 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.05 tok/s
- TTFT: 655.83 ms
- Total Duration: 53872.38 ms

## Delta (B - A)
- Throughput Δ: -1.42 tok/s
- TTFT Δ: -0.17 ms (positive = Agent B faster TTFT)
