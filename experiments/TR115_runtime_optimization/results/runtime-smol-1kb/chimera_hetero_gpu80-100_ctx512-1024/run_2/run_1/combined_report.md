# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 11.71s
- Sequential Estimate: 21.47s
- Speedup: 1.83x
- Efficiency: 91.7% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 43.36 tok/s
- TTFT: 883.22 ms
- Total Duration: 9761.56 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 56.59 tok/s
- TTFT: 762.03 ms
- Total Duration: 11709.45 ms

## Delta (B - A)
- Throughput Δ: +13.23 tok/s
- TTFT Δ: +121.20 ms (positive = Agent B faster TTFT)
