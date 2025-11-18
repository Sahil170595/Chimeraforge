# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 57.30s
- Sequential Estimate: 113.19s
- Speedup: 1.98x
- Efficiency: 98.8% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.58 tok/s
- TTFT: 702.74 ms
- Total Duration: 57275.59 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.56 tok/s
- TTFT: 909.01 ms
- Total Duration: 55866.66 ms

## Delta (B - A)
- Throughput Δ: -2.02 tok/s
- TTFT Δ: -206.27 ms (positive = Agent B faster TTFT)
