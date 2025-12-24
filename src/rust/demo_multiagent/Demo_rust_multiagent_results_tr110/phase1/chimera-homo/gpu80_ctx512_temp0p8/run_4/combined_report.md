# Rust Multi-Agent Report - Run 4

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 11.04s
- Sequential Estimate: 15.71s
- Speedup: 1.42x
- Efficiency: 71.2% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.09 tok/s
- TTFT: 240.37 ms
- Total Duration: 4677.37 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 99.82 tok/s
- TTFT: 4706.39 ms
- Total Duration: 11037.49 ms

## Delta (B - A)
- Throughput Δ: -0.28 tok/s
- TTFT Δ: -4466.03 ms (positive = Agent B faster TTFT)
