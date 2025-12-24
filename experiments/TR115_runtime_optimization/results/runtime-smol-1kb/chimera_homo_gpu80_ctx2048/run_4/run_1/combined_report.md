# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 13.01s
- Sequential Estimate: 23.82s
- Speedup: 1.83x
- Efficiency: 91.5% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.66 tok/s
- TTFT: 918.33 ms
- Total Duration: 10804.11 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 55.96 tok/s
- TTFT: 660.85 ms
- Total Duration: 13012.25 ms

## Delta (B - A)
- Throughput Δ: +13.30 tok/s
- TTFT Δ: +257.49 ms (positive = Agent B faster TTFT)
