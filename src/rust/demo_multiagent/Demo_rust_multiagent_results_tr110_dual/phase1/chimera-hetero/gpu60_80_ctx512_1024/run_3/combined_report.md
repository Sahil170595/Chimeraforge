# Rust Multi-Agent Report - Run 3

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 5.53s
- Sequential Estimate: 7.65s
- Speedup: 1.38x
- Efficiency: 69.1% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=60, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 88.52 tok/s
- TTFT: 303.28 ms
- Total Duration: 5529.08 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 42.00 tok/s
- TTFT: 304.61 ms
- Total Duration: 2117.20 ms

## Delta (B - A)
- Throughput Δ: -46.52 tok/s
- TTFT Δ: -1.34 ms (positive = Agent B faster TTFT)
