# Rust Multi-Agent Report - Run 2

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 54.82s
- Sequential Estimate: 108.41s
- Speedup: 1.98x
- Efficiency: 98.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=120, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.84 tok/s
- TTFT: 656.89 ms
- Total Duration: 54789.54 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=140, num_ctx=2048, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.92 tok/s
- TTFT: 527.12 ms
- Total Duration: 53568.37 ms

## Delta (B - A)
- Throughput Δ: -1.92 tok/s
- TTFT Δ: +129.77 ms (positive = Agent B faster TTFT)
