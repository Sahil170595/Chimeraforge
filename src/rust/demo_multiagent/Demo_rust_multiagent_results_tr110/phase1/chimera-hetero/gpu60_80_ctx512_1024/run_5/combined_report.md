# Rust Multi-Agent Report - Run 5

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 13.72s
- Sequential Estimate: 20.35s
- Speedup: 1.48x
- Efficiency: 74.2% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=60, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.41 tok/s
- TTFT: 9791.03 ms
- Total Duration: 13715.39 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 101.48 tok/s
- TTFT: 186.51 ms
- Total Duration: 6637.17 ms

## Delta (B - A)
- Throughput Δ: +1.07 tok/s
- TTFT Δ: +9604.51 ms (positive = Agent B faster TTFT)
