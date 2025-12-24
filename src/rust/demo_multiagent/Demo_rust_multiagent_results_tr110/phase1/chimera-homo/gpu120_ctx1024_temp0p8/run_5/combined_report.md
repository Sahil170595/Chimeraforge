# Rust Multi-Agent Report - Run 5

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 10.63s
- Sequential Estimate: 14.63s
- Speedup: 1.38x
- Efficiency: 68.8% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=120, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.34 tok/s
- TTFT: 214.91 ms
- Total Duration: 3994.12 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=120, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 99.78 tok/s
- TTFT: 4023.29 ms
- Total Duration: 10632.45 ms

## Delta (B - A)
- Throughput Δ: -0.56 tok/s
- TTFT Δ: -3808.37 ms (positive = Agent B faster TTFT)
