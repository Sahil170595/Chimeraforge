# Rust Multi-Agent Report - Run 4

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 13.68s
- Sequential Estimate: 17.53s
- Speedup: 1.28x
- Efficiency: 64.1% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 102.40 tok/s
- TTFT: 201.30 ms
- Total Duration: 3847.25 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=100, num_ctx=2048, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 100.69 tok/s
- TTFT: 7049.95 ms
- Total Duration: 13684.38 ms

## Delta (B - A)
- Throughput Δ: -1.70 tok/s
- TTFT Δ: -6848.65 ms (positive = Agent B faster TTFT)
