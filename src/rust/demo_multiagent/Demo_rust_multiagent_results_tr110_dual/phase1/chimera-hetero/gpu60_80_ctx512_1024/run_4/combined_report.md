# Rust Multi-Agent Report - Run 4

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 11.97s
- Sequential Estimate: 21.07s
- Speedup: 1.76x
- Efficiency: 88.1% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=60, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.29 tok/s
- TTFT: 273.37 ms
- Total Duration: 9109.76 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 58.08 tok/s
- TTFT: 313.65 ms
- Total Duration: 11965.21 ms

## Delta (B - A)
- Throughput Δ: +16.78 tok/s
- TTFT Δ: -40.28 ms (positive = Agent B faster TTFT)
