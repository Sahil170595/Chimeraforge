# Rust Multi-Agent Report – Run 4

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 73.02s
- Sequential Estimate: 124.92s
- Speedup: 1.71x
- Efficiency: 85.5% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 34.17 tok/s
- TTFT: 259.82 ms
- Total Duration: 73022.16 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 22.30 tok/s
- TTFT: 294.03 ms
- Total Duration: 51895.12 ms

## Delta (B - A)
- Throughput Δ: -11.87 tok/s
- TTFT Δ: -34.21 ms (positive = Agent B faster TTFT)
