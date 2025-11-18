# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 58.61s
- Sequential Estimate: 115.49s
- Speedup: 1.97x
- Efficiency: 98.5% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.30 tok/s
- TTFT: 606.29 ms
- Total Duration: 56861.55 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=2048, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.76 tok/s
- TTFT: 723.59 ms
- Total Duration: 58575.60 ms

## Delta (B - A)
- Throughput Δ: +1.46 tok/s
- TTFT Δ: -117.31 ms (positive = Agent B faster TTFT)
