# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 10.24s
- Sequential Estimate: 10.24s
- Speedup: 1.00x
- Efficiency: 50.0% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 122.22 tok/s
- TTFT: 845.94 ms
- Total Duration: 4476.17 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 121.81 tok/s
- TTFT: 614.43 ms
- Total Duration: 5762.80 ms

## Delta (B - A)
- Throughput Δ: -0.41 tok/s
- TTFT Δ: +231.51 ms (positive = Agent B faster TTFT)
