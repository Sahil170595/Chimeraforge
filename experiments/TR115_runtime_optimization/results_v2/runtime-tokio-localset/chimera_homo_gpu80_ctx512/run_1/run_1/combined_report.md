# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 80.34s
- Sequential Estimate: 130.20s
- Speedup: 1.62x
- Efficiency: 81.0% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 49.88 tok/s
- TTFT: 775.70 ms
- Total Duration: 49818.63 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 64.21 tok/s
- TTFT: 3050.71 ms
- Total Duration: 80307.52 ms

## Delta (B - A)
- Throughput Δ: +14.33 tok/s
- TTFT Δ: -2275.01 ms (positive = Agent B faster TTFT)
