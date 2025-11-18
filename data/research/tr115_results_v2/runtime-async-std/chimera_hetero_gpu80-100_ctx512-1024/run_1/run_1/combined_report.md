# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 55.56s
- Sequential Estimate: 55.55s
- Speedup: 1.00x
- Efficiency: 50.0% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 108.03 tok/s
- TTFT: 2904.56 ms
- Total Duration: 27561.61 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 107.89 tok/s
- TTFT: 3015.99 ms
- Total Duration: 27923.85 ms

## Delta (B - A)
- Throughput Δ: -0.14 tok/s
- TTFT Δ: -111.43 ms (positive = Agent B faster TTFT)
