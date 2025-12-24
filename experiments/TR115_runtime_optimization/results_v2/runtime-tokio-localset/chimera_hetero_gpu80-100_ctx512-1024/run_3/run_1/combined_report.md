# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 55.25s
- Sequential Estimate: 108.94s
- Speedup: 1.97x
- Efficiency: 98.6% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 43.00 tok/s
- TTFT: 819.09 ms
- Total Duration: 55222.96 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.99 tok/s
- TTFT: 801.77 ms
- Total Duration: 53657.71 ms

## Delta (B - A)
- Throughput Δ: -2.01 tok/s
- TTFT Δ: +17.32 ms (positive = Agent B faster TTFT)
