# Rust Multi-Agent Report - Run 5

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 11.01s
- Sequential Estimate: 15.46s
- Speedup: 1.40x
- Efficiency: 70.2% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=60, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 99.92 tok/s
- TTFT: 212.09 ms
- Total Duration: 4446.77 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=60, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.01 tok/s
- TTFT: 4475.56 ms
- Total Duration: 11008.86 ms

## Delta (B - A)
- Throughput Δ: +0.10 tok/s
- TTFT Δ: -4263.47 ms (positive = Agent B faster TTFT)
