# Rust Multi-Agent Report - Run 2

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 17.36s
- Sequential Estimate: 26.96s
- Speedup: 1.55x
- Efficiency: 77.7% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=60, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 99.55 tok/s
- TTFT: 12907.46 ms
- Total Duration: 17355.21 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 100.93 tok/s
- TTFT: 3294.15 ms
- Total Duration: 9609.59 ms

## Delta (B - A)
- Throughput Δ: +1.38 tok/s
- TTFT Δ: +9613.31 ms (positive = Agent B faster TTFT)
