# Rust Multi-Agent Report - Run 2

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 17.38s
- Sequential Estimate: 24.86s
- Speedup: 1.43x
- Efficiency: 71.5% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.50 tok/s
- TTFT: 3267.68 ms
- Total Duration: 7472.76 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=100, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 100.11 tok/s
- TTFT: 10633.77 ms
- Total Duration: 17383.89 ms

## Delta (B - A)
- Throughput Δ: -0.40 tok/s
- TTFT Δ: -7366.09 ms (positive = Agent B faster TTFT)
