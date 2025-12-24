# Rust Multi-Agent Report - Run 3

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 16.16s
- Sequential Estimate: 23.45s
- Speedup: 1.45x
- Efficiency: 72.6% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 101.59 tok/s
- TTFT: 3378.07 ms
- Total Duration: 7290.16 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=100, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 100.92 tok/s
- TTFT: 10223.25 ms
- Total Duration: 16156.15 ms

## Delta (B - A)
- Throughput Δ: -0.67 tok/s
- TTFT Δ: -6845.19 ms (positive = Agent B faster TTFT)
