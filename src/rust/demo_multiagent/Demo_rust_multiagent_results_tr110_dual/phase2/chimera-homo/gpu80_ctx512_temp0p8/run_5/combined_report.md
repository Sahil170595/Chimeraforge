# Rust Multi-Agent Report - Run 5

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 11.84s
- Sequential Estimate: 21.39s
- Speedup: 1.81x
- Efficiency: 90.3% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.28 tok/s
- TTFT: 264.33 ms
- Total Duration: 9547.39 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 55.02 tok/s
- TTFT: 306.81 ms
- Total Duration: 11837.61 ms

## Delta (B - A)
- Throughput Δ: +13.75 tok/s
- TTFT Δ: -42.48 ms (positive = Agent B faster TTFT)
