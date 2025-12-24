# Rust Multi-Agent Report - Run 5

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 13.03s
- Sequential Estimate: 24.31s
- Speedup: 1.87x
- Efficiency: 93.3% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=120, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 40.94 tok/s
- TTFT: 285.16 ms
- Total Duration: 11274.76 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=140, num_ctx=2048, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 50.26 tok/s
- TTFT: 303.40 ms
- Total Duration: 13031.47 ms

## Delta (B - A)
- Throughput Δ: +9.32 tok/s
- TTFT Δ: -18.25 ms (positive = Agent B faster TTFT)
