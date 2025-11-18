# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 63.81s
- Sequential Estimate: 125.41s
- Speedup: 1.97x
- Efficiency: 98.3% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 43.78 tok/s
- TTFT: 3937.17 ms
- Total Duration: 63789.92 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.90 tok/s
- TTFT: 3866.69 ms
- Total Duration: 61589.18 ms

## Delta (B - A)
- Throughput Δ: -2.88 tok/s
- TTFT Δ: +70.49 ms (positive = Agent B faster TTFT)
