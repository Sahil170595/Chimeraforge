# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 46.60s
- Sequential Estimate: 46.60s
- Speedup: 1.00x
- Efficiency: 50.0% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 108.84 tok/s
- TTFT: 571.73 ms
- Total Duration: 23931.23 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 107.79 tok/s
- TTFT: 599.38 ms
- Total Duration: 22605.43 ms

## Delta (B - A)
- Throughput Δ: -1.05 tok/s
- TTFT Δ: -27.65 ms (positive = Agent B faster TTFT)
