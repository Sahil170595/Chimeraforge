# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 59.64s
- Sequential Estimate: 117.52s
- Speedup: 1.97x
- Efficiency: 98.5% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.57 tok/s
- TTFT: 2598.63 ms
- Total Duration: 57864.12 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.85 tok/s
- TTFT: 2747.16 ms
- Total Duration: 59628.07 ms

## Delta (B - A)
- Throughput Δ: +1.28 tok/s
- TTFT Δ: -148.53 ms (positive = Agent B faster TTFT)
