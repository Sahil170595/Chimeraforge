# Rust Multi-Agent Report - Run 3

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 13.15s
- Sequential Estimate: 23.68s
- Speedup: 1.80x
- Efficiency: 90.0% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.09 tok/s
- TTFT: 317.89 ms
- Total Duration: 10527.95 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 54.94 tok/s
- TTFT: 268.20 ms
- Total Duration: 13153.81 ms

## Delta (B - A)
- Throughput Δ: +13.85 tok/s
- TTFT Δ: +49.69 ms (positive = Agent B faster TTFT)
