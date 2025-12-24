# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 11.45s
- Sequential Estimate: 20.81s
- Speedup: 1.82x
- Efficiency: 90.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.42 tok/s
- TTFT: 694.98 ms
- Total Duration: 9358.14 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 57.63 tok/s
- TTFT: 574.07 ms
- Total Duration: 11451.96 ms

## Delta (B - A)
- Throughput Δ: +15.21 tok/s
- TTFT Δ: +120.91 ms (positive = Agent B faster TTFT)
