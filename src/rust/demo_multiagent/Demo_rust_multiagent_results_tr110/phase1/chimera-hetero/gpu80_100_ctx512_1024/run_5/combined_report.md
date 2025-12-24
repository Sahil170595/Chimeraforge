# Rust Multi-Agent Report - Run 5

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 16.34s
- Sequential Estimate: 23.06s
- Speedup: 1.41x
- Efficiency: 70.6% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 101.09 tok/s
- TTFT: 3292.04 ms
- Total Duration: 6720.02 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=100, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 101.11 tok/s
- TTFT: 10008.92 ms
- Total Duration: 16343.76 ms

## Delta (B - A)
- Throughput Δ: +0.02 tok/s
- TTFT Δ: -6716.88 ms (positive = Agent B faster TTFT)
