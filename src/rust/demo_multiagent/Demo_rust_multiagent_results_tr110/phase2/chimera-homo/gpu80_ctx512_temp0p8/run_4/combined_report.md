# Rust Multi-Agent Report - Run 4

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 10.95s
- Sequential Estimate: 14.87s
- Speedup: 1.36x
- Efficiency: 67.9% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.26 tok/s
- TTFT: 207.70 ms
- Total Duration: 3921.87 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.97 tok/s
- TTFT: 3948.79 ms
- Total Duration: 10947.18 ms

## Delta (B - A)
- Throughput Δ: +0.71 tok/s
- TTFT Δ: -3741.09 ms (positive = Agent B faster TTFT)
