# Rust Multi-Agent Report - Run 5

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 10.73s
- Sequential Estimate: 15.25s
- Speedup: 1.42x
- Efficiency: 71.1% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.50 tok/s
- TTFT: 211.12 ms
- Total Duration: 4521.21 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.10 tok/s
- TTFT: 4550.14 ms
- Total Duration: 10727.17 ms

## Delta (B - A)
- Throughput Δ: -0.40 tok/s
- TTFT Δ: -4339.02 ms (positive = Agent B faster TTFT)
