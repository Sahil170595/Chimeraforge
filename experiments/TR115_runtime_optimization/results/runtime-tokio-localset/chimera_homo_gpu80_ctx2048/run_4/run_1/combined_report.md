# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 13.30s
- Sequential Estimate: 24.49s
- Speedup: 1.84x
- Efficiency: 92.1% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.38 tok/s
- TTFT: 655.74 ms
- Total Duration: 11192.57 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 54.96 tok/s
- TTFT: 568.11 ms
- Total Duration: 13298.56 ms

## Delta (B - A)
- Throughput Δ: +12.58 tok/s
- TTFT Δ: +87.63 ms (positive = Agent B faster TTFT)
