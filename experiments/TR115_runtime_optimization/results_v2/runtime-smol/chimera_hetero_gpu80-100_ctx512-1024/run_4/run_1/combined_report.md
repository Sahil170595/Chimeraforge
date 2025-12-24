# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 60.22s
- Sequential Estimate: 119.58s
- Speedup: 1.99x
- Efficiency: 99.3% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.82 tok/s
- TTFT: 931.76 ms
- Total Duration: 58594.92 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 39.99 tok/s
- TTFT: 967.44 ms
- Total Duration: 57731.81 ms

## Delta (B - A)
- Throughput Δ: -0.83 tok/s
- TTFT Δ: -35.67 ms (positive = Agent B faster TTFT)
