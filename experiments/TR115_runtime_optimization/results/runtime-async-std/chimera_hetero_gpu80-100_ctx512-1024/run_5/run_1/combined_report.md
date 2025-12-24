# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 5.84s
- Sequential Estimate: 5.84s
- Speedup: 1.00x
- Efficiency: 50.0% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 122.61 tok/s
- TTFT: 857.89 ms
- Total Duration: 4766.46 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 124.37 tok/s
- TTFT: 569.61 ms
- Total Duration: 1071.22 ms

## Delta (B - A)
- Throughput Δ: +1.76 tok/s
- TTFT Δ: +288.28 ms (positive = Agent B faster TTFT)
