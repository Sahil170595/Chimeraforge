# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 55.10s
- Sequential Estimate: 109.88s
- Speedup: 1.99x
- Efficiency: 99.7% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.10 tok/s
- TTFT: 820.58 ms
- Total Duration: 54758.14 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.15 tok/s
- TTFT: 669.85 ms
- Total Duration: 55066.20 ms

## Delta (B - A)
- Throughput Δ: +0.05 tok/s
- TTFT Δ: +150.73 ms (positive = Agent B faster TTFT)
