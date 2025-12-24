# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 55.88s
- Sequential Estimate: 111.09s
- Speedup: 1.99x
- Efficiency: 99.4% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.72 tok/s
- TTFT: 830.39 ms
- Total Duration: 55845.91 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.96 tok/s
- TTFT: 828.01 ms
- Total Duration: 55179.04 ms

## Delta (B - A)
- Throughput Δ: -0.76 tok/s
- TTFT Δ: +2.38 ms (positive = Agent B faster TTFT)
