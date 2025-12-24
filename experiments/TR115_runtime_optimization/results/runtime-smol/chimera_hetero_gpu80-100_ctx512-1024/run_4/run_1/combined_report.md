# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 11.75s
- Sequential Estimate: 21.64s
- Speedup: 1.84x
- Efficiency: 92.1% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.56 tok/s
- TTFT: 707.69 ms
- Total Duration: 9897.43 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 55.66 tok/s
- TTFT: 580.21 ms
- Total Duration: 11746.35 ms

## Delta (B - A)
- Throughput Δ: +13.10 tok/s
- TTFT Δ: +127.48 ms (positive = Agent B faster TTFT)
