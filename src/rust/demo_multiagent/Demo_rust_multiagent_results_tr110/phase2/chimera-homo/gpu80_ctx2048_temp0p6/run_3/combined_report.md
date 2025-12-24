# Rust Multi-Agent Report - Run 3

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 11.12s
- Sequential Estimate: 15.59s
- Speedup: 1.40x
- Efficiency: 70.1% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.61 tok/s
- TTFT: 199.31 ms
- Total Duration: 4464.33 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 101.00 tok/s
- TTFT: 4492.77 ms
- Total Duration: 11120.68 ms

## Delta (B - A)
- Throughput Δ: +0.38 tok/s
- TTFT Δ: -4293.46 ms (positive = Agent B faster TTFT)
