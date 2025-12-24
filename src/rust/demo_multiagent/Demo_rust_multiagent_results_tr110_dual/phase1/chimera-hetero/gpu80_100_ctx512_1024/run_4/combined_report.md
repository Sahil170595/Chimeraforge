# Rust Multi-Agent Report - Run 4

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 12.66s
- Sequential Estimate: 23.27s
- Speedup: 1.84x
- Efficiency: 91.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.21 tok/s
- TTFT: 269.73 ms
- Total Duration: 10614.68 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=100, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 52.39 tok/s
- TTFT: 296.03 ms
- Total Duration: 12655.48 ms

## Delta (B - A)
- Throughput Δ: +11.18 tok/s
- TTFT Δ: -26.30 ms (positive = Agent B faster TTFT)
