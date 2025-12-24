# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 18.21s
- Sequential Estimate: 18.21s
- Speedup: 1.00x
- Efficiency: 50.0% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 123.04 tok/s
- TTFT: 4633.08 ms
- Total Duration: 7699.76 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 120.72 tok/s
- TTFT: 4847.57 ms
- Total Duration: 10509.99 ms

## Delta (B - A)
- Throughput Δ: -2.31 tok/s
- TTFT Δ: -214.49 ms (positive = Agent B faster TTFT)
