# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 54.23s
- Sequential Estimate: 107.29s
- Speedup: 1.98x
- Efficiency: 98.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.56 tok/s
- TTFT: 650.11 ms
- Total Duration: 54216.73 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.48 tok/s
- TTFT: 843.38 ms
- Total Duration: 53040.71 ms

## Delta (B - A)
- Throughput Δ: -2.08 tok/s
- TTFT Δ: -193.27 ms (positive = Agent B faster TTFT)
