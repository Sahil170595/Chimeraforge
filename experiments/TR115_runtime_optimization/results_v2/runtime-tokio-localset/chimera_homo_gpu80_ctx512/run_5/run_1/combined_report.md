# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 56.60s
- Sequential Estimate: 112.86s
- Speedup: 1.99x
- Efficiency: 99.7% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.21 tok/s
- TTFT: 678.84 ms
- Total Duration: 56580.91 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.70 tok/s
- TTFT: 837.70 ms
- Total Duration: 56249.27 ms

## Delta (B - A)
- Throughput Δ: -0.51 tok/s
- TTFT Δ: -158.86 ms (positive = Agent B faster TTFT)
