# Rust Multi-Agent Report - Run 5

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 11.56s
- Sequential Estimate: 20.97s
- Speedup: 1.81x
- Efficiency: 90.7% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.45 tok/s
- TTFT: 279.18 ms
- Total Duration: 9407.82 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 54.69 tok/s
- TTFT: 306.84 ms
- Total Duration: 11562.35 ms

## Delta (B - A)
- Throughput Δ: +13.24 tok/s
- TTFT Δ: -27.66 ms (positive = Agent B faster TTFT)
