# Rust Multi-Agent Report - Run 5

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 58.21s
- Sequential Estimate: 116.28s
- Speedup: 2.00x
- Efficiency: 99.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.24 tok/s
- TTFT: 649.37 ms
- Total Duration: 58164.52 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.13 tok/s
- TTFT: 650.33 ms
- Total Duration: 58021.92 ms

## Delta (B - A)
- Throughput Δ: -0.11 tok/s
- TTFT Δ: -0.96 ms (positive = Agent B faster TTFT)
