# Rust Multi-Agent Report - Run 2

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 53.56s
- Sequential Estimate: 105.03s
- Speedup: 1.96x
- Efficiency: 98.0% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 43.81 tok/s
- TTFT: 666.74 ms
- Total Duration: 53497.76 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.99 tok/s
- TTFT: 632.79 ms
- Total Duration: 51405.97 ms

## Delta (B - A)
- Throughput Δ: -2.82 tok/s
- TTFT Δ: +33.95 ms (positive = Agent B faster TTFT)
