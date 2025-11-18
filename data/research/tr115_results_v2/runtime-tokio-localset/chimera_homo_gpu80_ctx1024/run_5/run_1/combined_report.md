# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 53.50s
- Sequential Estimate: 106.38s
- Speedup: 1.99x
- Efficiency: 99.4% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.88 tok/s
- TTFT: 820.06 ms
- Total Duration: 53473.53 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.07 tok/s
- TTFT: 735.61 ms
- Total Duration: 52851.75 ms

## Delta (B - A)
- Throughput Δ: -0.81 tok/s
- TTFT Δ: +84.45 ms (positive = Agent B faster TTFT)
