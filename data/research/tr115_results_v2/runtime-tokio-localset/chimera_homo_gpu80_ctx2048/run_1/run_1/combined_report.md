# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 38.68s
- Sequential Estimate: 66.86s
- Speedup: 1.73x
- Efficiency: 86.4% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 20.89 tok/s
- TTFT: 814.64 ms
- Total Duration: 28147.76 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 71.35 tok/s
- TTFT: 823.14 ms
- Total Duration: 38643.91 ms

## Delta (B - A)
- Throughput Δ: +50.46 tok/s
- TTFT Δ: -8.51 ms (positive = Agent B faster TTFT)
