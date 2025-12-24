# Rust Multi-Agent Report - Run 4

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 5.70s
- Sequential Estimate: 7.91s
- Speedup: 1.39x
- Efficiency: 69.4% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=120, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 87.55 tok/s
- TTFT: 273.81 ms
- Total Duration: 5699.72 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=140, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 42.14 tok/s
- TTFT: 306.57 ms
- Total Duration: 2214.80 ms

## Delta (B - A)
- Throughput Δ: -45.41 tok/s
- TTFT Δ: -32.76 ms (positive = Agent B faster TTFT)
