# Rust Multi-Agent Report - Run 5

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 57.60s
- Sequential Estimate: 115.04s
- Speedup: 2.00x
- Efficiency: 99.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=60, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.21 tok/s
- TTFT: 678.70 ms
- Total Duration: 57407.50 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=2048, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.32 tok/s
- TTFT: 670.14 ms
- Total Duration: 57566.35 ms

## Delta (B - A)
- Throughput Δ: +0.11 tok/s
- TTFT Δ: +8.56 ms (positive = Agent B faster TTFT)
