# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 13.29s
- Sequential Estimate: 25.03s
- Speedup: 1.88x
- Efficiency: 94.2% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.50 tok/s
- TTFT: 614.05 ms
- Total Duration: 11742.45 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 51.41 tok/s
- TTFT: 569.64 ms
- Total Duration: 13284.68 ms

## Delta (B - A)
- Throughput Δ: +8.90 tok/s
- TTFT Δ: +44.41 ms (positive = Agent B faster TTFT)
