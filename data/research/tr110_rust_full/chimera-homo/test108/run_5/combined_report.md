# Rust Multi-Agent Report - Run 5

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 57.80s
- Sequential Estimate: 113.68s
- Speedup: 1.97x
- Efficiency: 98.3% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.90 tok/s
- TTFT: 694.47 ms
- Total Duration: 55838.35 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 43.57 tok/s
- TTFT: 659.92 ms
- Total Duration: 57762.50 ms

## Delta (B - A)
- Throughput Δ: +2.67 tok/s
- TTFT Δ: +34.55 ms (positive = Agent B faster TTFT)
