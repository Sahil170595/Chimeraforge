# Rust Multi-Agent Report - Run 3

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 11.34s
- Sequential Estimate: 18.52s
- Speedup: 1.63x
- Efficiency: 81.7% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.97 tok/s
- TTFT: 7215.48 ms
- Total Duration: 11336.72 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.44 tok/s
- TTFT: 210.93 ms
- Total Duration: 7187.87 ms

## Delta (B - A)
- Throughput Δ: -0.53 tok/s
- TTFT Δ: +7004.55 ms (positive = Agent B faster TTFT)
