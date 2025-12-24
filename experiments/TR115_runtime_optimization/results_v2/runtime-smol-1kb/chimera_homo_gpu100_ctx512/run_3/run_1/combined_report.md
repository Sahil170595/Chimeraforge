# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 56.02s
- Sequential Estimate: 110.37s
- Speedup: 1.97x
- Efficiency: 98.5% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.08 tok/s
- TTFT: 1045.49 ms
- Total Duration: 54317.27 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 43.33 tok/s
- TTFT: 1062.95 ms
- Total Duration: 55974.34 ms

## Delta (B - A)
- Throughput Δ: +2.25 tok/s
- TTFT Δ: -17.46 ms (positive = Agent B faster TTFT)
