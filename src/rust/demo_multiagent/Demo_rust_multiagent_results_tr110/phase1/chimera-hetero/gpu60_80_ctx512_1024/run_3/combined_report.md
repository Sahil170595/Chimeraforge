# Rust Multi-Agent Report - Run 3

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 13.33s
- Sequential Estimate: 17.32s
- Speedup: 1.30x
- Efficiency: 64.9% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=60, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 103.27 tok/s
- TTFT: 204.55 ms
- Total Duration: 3982.81 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 100.79 tok/s
- TTFT: 7184.53 ms
- Total Duration: 13333.70 ms

## Delta (B - A)
- Throughput Δ: -2.49 tok/s
- TTFT Δ: -6979.97 ms (positive = Agent B faster TTFT)
