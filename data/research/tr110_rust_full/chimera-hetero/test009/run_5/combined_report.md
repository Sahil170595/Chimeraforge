# Rust Multi-Agent Report - Run 5

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 56.47s
- Sequential Estimate: 111.71s
- Speedup: 1.98x
- Efficiency: 98.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.72 tok/s
- TTFT: 540.11 ms
- Total Duration: 55224.47 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.45 tok/s
- TTFT: 662.90 ms
- Total Duration: 56458.56 ms

## Delta (B - A)
- Throughput Δ: +1.74 tok/s
- TTFT Δ: -122.79 ms (positive = Agent B faster TTFT)
