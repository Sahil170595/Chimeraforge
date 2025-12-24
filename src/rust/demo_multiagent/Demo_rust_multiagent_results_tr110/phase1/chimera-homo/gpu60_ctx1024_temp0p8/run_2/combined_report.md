# Rust Multi-Agent Report - Run 2

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 11.60s
- Sequential Estimate: 15.81s
- Speedup: 1.36x
- Efficiency: 68.1% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=60, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.51 tok/s
- TTFT: 203.49 ms
- Total Duration: 4205.22 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=60, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.12 tok/s
- TTFT: 4237.40 ms
- Total Duration: 11604.50 ms

## Delta (B - A)
- Throughput Δ: -0.39 tok/s
- TTFT Δ: -4033.90 ms (positive = Agent B faster TTFT)
