# Rust Multi-Agent Report - Run 5

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 55.61s
- Sequential Estimate: 109.72s
- Speedup: 1.97x
- Efficiency: 98.7% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.6, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.06 tok/s
- TTFT: 682.61 ms
- Total Duration: 54091.39 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=0.6, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 43.03 tok/s
- TTFT: 665.43 ms
- Total Duration: 55575.84 ms

## Delta (B - A)
- Throughput Δ: +1.97 tok/s
- TTFT Δ: +17.18 ms (positive = Agent B faster TTFT)
