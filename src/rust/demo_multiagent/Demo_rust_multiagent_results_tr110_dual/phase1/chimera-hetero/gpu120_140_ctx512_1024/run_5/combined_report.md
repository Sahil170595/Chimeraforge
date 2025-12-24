# Rust Multi-Agent Report - Run 5

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 12.19s
- Sequential Estimate: 21.55s
- Speedup: 1.77x
- Efficiency: 88.4% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=120, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.28 tok/s
- TTFT: 268.60 ms
- Total Duration: 9353.50 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=140, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 57.46 tok/s
- TTFT: 317.39 ms
- Total Duration: 12192.12 ms

## Delta (B - A)
- Throughput Δ: +16.18 tok/s
- TTFT Δ: -48.78 ms (positive = Agent B faster TTFT)
