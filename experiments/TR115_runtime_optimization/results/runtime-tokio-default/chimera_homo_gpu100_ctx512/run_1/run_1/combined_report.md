# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 20.10s
- Sequential Estimate: 37.64s
- Speedup: 1.87x
- Efficiency: 93.6% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.67 tok/s
- TTFT: 7803.06 ms
- Total Duration: 17540.78 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 55.58 tok/s
- TTFT: 8080.47 ms
- Total Duration: 20102.78 ms

## Delta (B - A)
- Throughput Δ: +12.91 tok/s
- TTFT Δ: -277.40 ms (positive = Agent B faster TTFT)
