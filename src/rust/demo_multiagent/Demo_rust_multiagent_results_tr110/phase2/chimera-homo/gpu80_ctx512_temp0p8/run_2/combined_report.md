# Rust Multi-Agent Report - Run 2

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 10.84s
- Sequential Estimate: 17.44s
- Speedup: 1.61x
- Efficiency: 80.4% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 102.35 tok/s
- TTFT: 6621.71 ms
- Total Duration: 10843.79 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 101.13 tok/s
- TTFT: 239.33 ms
- Total Duration: 6592.48 ms

## Delta (B - A)
- Throughput Δ: -1.22 tok/s
- TTFT Δ: +6382.38 ms (positive = Agent B faster TTFT)
