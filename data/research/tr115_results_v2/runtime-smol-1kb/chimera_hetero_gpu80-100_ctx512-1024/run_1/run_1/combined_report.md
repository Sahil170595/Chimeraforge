# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 63.63s
- Sequential Estimate: 126.44s
- Speedup: 1.99x
- Efficiency: 99.4% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.25 tok/s
- TTFT: 4407.24 ms
- Total Duration: 62782.01 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.29 tok/s
- TTFT: 4395.32 ms
- Total Duration: 63589.90 ms

## Delta (B - A)
- Throughput Δ: +1.04 tok/s
- TTFT Δ: +11.92 ms (positive = Agent B faster TTFT)
