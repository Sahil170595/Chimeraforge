# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 13.56s
- Sequential Estimate: 20.98s
- Speedup: 1.55x
- Efficiency: 77.4% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 102.34 tok/s
- TTFT: 3897.45 ms
- Total Duration: 7422.82 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 102.05 tok/s
- TTFT: 7463.75 ms
- Total Duration: 13560.69 ms

## Delta (B - A)
- Throughput Δ: -0.29 tok/s
- TTFT Δ: -3566.29 ms (positive = Agent B faster TTFT)
