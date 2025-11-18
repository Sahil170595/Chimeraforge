# Rust Multi-Agent Report - Run 5

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 59.37s
- Sequential Estimate: 117.79s
- Speedup: 1.98x
- Efficiency: 99.2% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=60, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.14 tok/s
- TTFT: 675.93 ms
- Total Duration: 58397.78 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.31 tok/s
- TTFT: 666.98 ms
- Total Duration: 59338.69 ms

## Delta (B - A)
- Throughput Δ: +1.17 tok/s
- TTFT Δ: +8.95 ms (positive = Agent B faster TTFT)
