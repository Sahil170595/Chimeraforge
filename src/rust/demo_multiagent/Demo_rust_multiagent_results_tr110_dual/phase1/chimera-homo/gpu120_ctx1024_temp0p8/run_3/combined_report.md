# Rust Multi-Agent Report - Run 3

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 13.17s
- Sequential Estimate: 23.81s
- Speedup: 1.81x
- Efficiency: 90.4% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=120, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.16 tok/s
- TTFT: 305.45 ms
- Total Duration: 10645.15 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=120, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 54.43 tok/s
- TTFT: 303.68 ms
- Total Duration: 13169.80 ms

## Delta (B - A)
- Throughput Δ: +13.27 tok/s
- TTFT Δ: +1.76 ms (positive = Agent B faster TTFT)
