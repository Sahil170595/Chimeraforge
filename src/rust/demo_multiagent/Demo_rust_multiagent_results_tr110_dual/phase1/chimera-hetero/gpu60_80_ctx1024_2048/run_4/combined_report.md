# Rust Multi-Agent Report - Run 4

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 5.35s
- Sequential Estimate: 7.73s
- Speedup: 1.44x
- Efficiency: 72.2% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=60, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 83.86 tok/s
- TTFT: 255.75 ms
- Total Duration: 5353.45 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=2048, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 41.59 tok/s
- TTFT: 339.14 ms
- Total Duration: 2371.82 ms

## Delta (B - A)
- Throughput Δ: -42.27 tok/s
- TTFT Δ: -83.39 ms (positive = Agent B faster TTFT)
