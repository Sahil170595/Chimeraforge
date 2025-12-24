# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 10.51s
- Sequential Estimate: 10.51s
- Speedup: 1.00x
- Efficiency: 50.0% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 122.51 tok/s
- TTFT: 792.00 ms
- Total Duration: 4356.63 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 121.41 tok/s
- TTFT: 580.43 ms
- Total Duration: 6152.01 ms

## Delta (B - A)
- Throughput Δ: -1.10 tok/s
- TTFT Δ: +211.57 ms (positive = Agent B faster TTFT)
