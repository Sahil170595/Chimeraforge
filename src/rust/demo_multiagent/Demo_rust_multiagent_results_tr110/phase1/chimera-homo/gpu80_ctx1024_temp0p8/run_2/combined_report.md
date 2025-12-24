# Rust Multi-Agent Report - Run 2

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 11.68s
- Sequential Estimate: 18.70s
- Speedup: 1.60x
- Efficiency: 80.0% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.08 tok/s
- TTFT: 7044.54 ms
- Total Duration: 11683.54 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.01 tok/s
- TTFT: 192.45 ms
- Total Duration: 7015.17 ms

## Delta (B - A)
- Throughput Δ: -0.08 tok/s
- TTFT Δ: +6852.09 ms (positive = Agent B faster TTFT)
