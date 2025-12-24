# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 10.57s
- Sequential Estimate: 14.82s
- Speedup: 1.40x
- Efficiency: 70.1% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.40 tok/s
- TTFT: 263.28 ms
- Total Duration: 4249.23 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.39 tok/s
- TTFT: 4279.94 ms
- Total Duration: 10568.70 ms

## Delta (B - A)
- Throughput Δ: -0.00 tok/s
- TTFT Δ: -4016.66 ms (positive = Agent B faster TTFT)
