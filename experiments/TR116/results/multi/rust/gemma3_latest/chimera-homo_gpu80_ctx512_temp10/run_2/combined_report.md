# Rust Multi-Agent Report – Run 2

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 55.44s
- Sequential Estimate: 110.73s
- Speedup: 2.00x
- Efficiency: 99.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.85 tok/s
- TTFT: 627.74 ms
- Total Duration: 55286.00 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.30 tok/s
- TTFT: 463.73 ms
- Total Duration: 55440.32 ms

## Delta (B - A)
- Throughput Δ: +0.45 tok/s
- TTFT Δ: +164.01 ms (positive = Agent B faster TTFT)
