# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 55.66s
- Sequential Estimate: 110.54s
- Speedup: 1.99x
- Efficiency: 99.3% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.92 tok/s
- TTFT: 845.98 ms
- Total Duration: 55608.48 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.73 tok/s
- TTFT: 799.76 ms
- Total Duration: 54832.31 ms

## Delta (B - A)
- Throughput Δ: -1.18 tok/s
- TTFT Δ: +46.22 ms (positive = Agent B faster TTFT)
