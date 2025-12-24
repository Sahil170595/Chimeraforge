# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 12.45s
- Sequential Estimate: 22.89s
- Speedup: 1.84x
- Efficiency: 92.0% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.58 tok/s
- TTFT: 679.63 ms
- Total Duration: 10447.07 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 55.41 tok/s
- TTFT: 581.92 ms
- Total Duration: 12445.79 ms

## Delta (B - A)
- Throughput Δ: +12.83 tok/s
- TTFT Δ: +97.71 ms (positive = Agent B faster TTFT)
