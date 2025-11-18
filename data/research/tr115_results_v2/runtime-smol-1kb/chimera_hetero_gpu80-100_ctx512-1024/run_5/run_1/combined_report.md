# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 56.04s
- Sequential Estimate: 110.71s
- Speedup: 1.98x
- Efficiency: 98.8% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 43.05 tok/s
- TTFT: 1062.52 ms
- Total Duration: 56010.69 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.87 tok/s
- TTFT: 875.81 ms
- Total Duration: 54643.67 ms

## Delta (B - A)
- Throughput Δ: -2.18 tok/s
- TTFT Δ: +186.71 ms (positive = Agent B faster TTFT)
