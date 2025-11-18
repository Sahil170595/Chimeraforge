# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 58.84s
- Sequential Estimate: 117.21s
- Speedup: 1.99x
- Efficiency: 99.6% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.87 tok/s
- TTFT: 849.25 ms
- Total Duration: 58793.28 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.44 tok/s
- TTFT: 857.79 ms
- Total Duration: 58316.54 ms

## Delta (B - A)
- Throughput Δ: -0.43 tok/s
- TTFT Δ: -8.54 ms (positive = Agent B faster TTFT)
