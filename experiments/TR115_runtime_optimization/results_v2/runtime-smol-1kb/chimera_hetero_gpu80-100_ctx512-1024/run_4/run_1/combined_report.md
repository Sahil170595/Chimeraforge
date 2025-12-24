# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 58.27s
- Sequential Estimate: 116.33s
- Speedup: 2.00x
- Efficiency: 99.8% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.42 tok/s
- TTFT: 1063.99 ms
- Total Duration: 58219.78 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.12 tok/s
- TTFT: 988.92 ms
- Total Duration: 58019.39 ms

## Delta (B - A)
- Throughput Δ: -0.30 tok/s
- TTFT Δ: +75.07 ms (positive = Agent B faster TTFT)
