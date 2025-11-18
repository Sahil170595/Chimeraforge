# Rust Multi-Agent Report - Run 5

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 55.32s
- Sequential Estimate: 109.49s
- Speedup: 1.98x
- Efficiency: 99.0% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.95 tok/s
- TTFT: 673.18 ms
- Total Duration: 54136.63 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=2048, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.56 tok/s
- TTFT: 655.38 ms
- Total Duration: 55292.65 ms

## Delta (B - A)
- Throughput Δ: +1.61 tok/s
- TTFT Δ: +17.80 ms (positive = Agent B faster TTFT)
