# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 11.40s
- Sequential Estimate: 20.59s
- Speedup: 1.81x
- Efficiency: 90.3% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.63 tok/s
- TTFT: 637.85 ms
- Total Duration: 9190.68 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 58.14 tok/s
- TTFT: 553.49 ms
- Total Duration: 11397.26 ms

## Delta (B - A)
- Throughput Δ: +15.51 tok/s
- TTFT Δ: +84.36 ms (positive = Agent B faster TTFT)
