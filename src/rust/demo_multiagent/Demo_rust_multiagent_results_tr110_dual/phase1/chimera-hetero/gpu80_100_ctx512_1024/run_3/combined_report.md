# Rust Multi-Agent Report - Run 3

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 11.55s
- Sequential Estimate: 21.00s
- Speedup: 1.82x
- Efficiency: 90.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.24 tok/s
- TTFT: 252.38 ms
- Total Duration: 9447.30 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=100, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 53.66 tok/s
- TTFT: 320.91 ms
- Total Duration: 11550.48 ms

## Delta (B - A)
- Throughput Δ: +12.42 tok/s
- TTFT Δ: -68.53 ms (positive = Agent B faster TTFT)
