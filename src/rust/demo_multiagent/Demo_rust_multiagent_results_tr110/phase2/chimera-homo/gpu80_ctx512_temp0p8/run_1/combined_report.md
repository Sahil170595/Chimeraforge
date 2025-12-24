# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 11.20s
- Sequential Estimate: 18.24s
- Speedup: 1.63x
- Efficiency: 81.4% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 103.05 tok/s
- TTFT: 7070.67 ms
- Total Duration: 11195.79 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 101.33 tok/s
- TTFT: 207.28 ms
- Total Duration: 7041.92 ms

## Delta (B - A)
- Throughput Δ: -1.72 tok/s
- TTFT Δ: +6863.39 ms (positive = Agent B faster TTFT)
