# Rust Multi-Agent Report - Run 4

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 54.61s
- Sequential Estimate: 108.76s
- Speedup: 1.99x
- Efficiency: 99.6% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=120, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.89 tok/s
- TTFT: 554.94 ms
- Total Duration: 54112.30 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=140, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.62 tok/s
- TTFT: 654.00 ms
- Total Duration: 54583.52 ms

## Delta (B - A)
- Throughput Δ: +0.73 tok/s
- TTFT Δ: -99.06 ms (positive = Agent B faster TTFT)
