# Rust Multi-Agent Report - Run 2

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 4.45s
- Sequential Estimate: 6.06s
- Speedup: 1.36x
- Efficiency: 68.1% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=120, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 90.17 tok/s
- TTFT: 248.08 ms
- Total Duration: 4451.44 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=140, num_ctx=2048, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 41.58 tok/s
- TTFT: 304.80 ms
- Total Duration: 1612.68 ms

## Delta (B - A)
- Throughput Δ: -48.59 tok/s
- TTFT Δ: -56.72 ms (positive = Agent B faster TTFT)
