# Rust Multi-Agent Report - Run 2

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 13.08s
- Sequential Estimate: 24.10s
- Speedup: 1.84x
- Efficiency: 92.1% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 40.98 tok/s
- TTFT: 318.98 ms
- Total Duration: 11019.98 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=100, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 51.84 tok/s
- TTFT: 318.55 ms
- Total Duration: 13081.70 ms

## Delta (B - A)
- Throughput Δ: +10.87 tok/s
- TTFT Δ: +0.43 ms (positive = Agent B faster TTFT)
