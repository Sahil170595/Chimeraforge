# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 56.30s
- Sequential Estimate: 110.54s
- Speedup: 1.96x
- Efficiency: 98.2% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=0.6, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 43.55 tok/s
- TTFT: 730.04 ms
- Total Duration: 56283.11 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=2048, temp=0.6, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.88 tok/s
- TTFT: 826.59 ms
- Total Duration: 54216.78 ms

## Delta (B - A)
- Throughput Δ: -2.67 tok/s
- TTFT Δ: -96.55 ms (positive = Agent B faster TTFT)
