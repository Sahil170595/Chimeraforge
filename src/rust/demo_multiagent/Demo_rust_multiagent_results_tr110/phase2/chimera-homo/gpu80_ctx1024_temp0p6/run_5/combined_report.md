# Rust Multi-Agent Report - Run 5

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 11.05s
- Sequential Estimate: 17.92s
- Speedup: 1.62x
- Efficiency: 81.1% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.11 tok/s
- TTFT: 6908.87 ms
- Total Duration: 11045.03 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.54 tok/s
- TTFT: 220.46 ms
- Total Duration: 6878.91 ms

## Delta (B - A)
- Throughput Δ: +0.43 tok/s
- TTFT Δ: +6688.41 ms (positive = Agent B faster TTFT)
