# Rust Multi-Agent Report - Run 2

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 57.61s
- Sequential Estimate: 114.96s
- Speedup: 2.00x
- Efficiency: 99.8% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=120, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.81 tok/s
- TTFT: 522.37 ms
- Total Duration: 57581.94 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=120, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.81 tok/s
- TTFT: 653.10 ms
- Total Duration: 57318.04 ms

## Delta (B - A)
- Throughput Δ: +0.01 tok/s
- TTFT Δ: -130.74 ms (positive = Agent B faster TTFT)
