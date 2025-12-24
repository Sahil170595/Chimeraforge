# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 56.91s
- Sequential Estimate: 113.04s
- Speedup: 1.99x
- Efficiency: 99.3% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.10 tok/s
- TTFT: 1030.01 ms
- Total Duration: 56100.08 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.90 tok/s
- TTFT: 1049.15 ms
- Total Duration: 56883.75 ms

## Delta (B - A)
- Throughput Δ: +0.80 tok/s
- TTFT Δ: -19.14 ms (positive = Agent B faster TTFT)
