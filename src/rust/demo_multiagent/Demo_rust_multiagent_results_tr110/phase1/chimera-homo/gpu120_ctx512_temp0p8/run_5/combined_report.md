# Rust Multi-Agent Report - Run 5

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 11.55s
- Sequential Estimate: 18.78s
- Speedup: 1.63x
- Efficiency: 81.3% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=120, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 99.87 tok/s
- TTFT: 7257.04 ms
- Total Duration: 11554.45 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=120, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 99.48 tok/s
- TTFT: 177.54 ms
- Total Duration: 7228.57 ms

## Delta (B - A)
- Throughput Δ: -0.40 tok/s
- TTFT Δ: +7079.50 ms (positive = Agent B faster TTFT)
