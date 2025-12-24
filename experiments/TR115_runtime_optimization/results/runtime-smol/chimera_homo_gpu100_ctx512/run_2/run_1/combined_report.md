# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 12.51s
- Sequential Estimate: 21.78s
- Speedup: 1.74x
- Efficiency: 87.0% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.76 tok/s
- TTFT: 688.60 ms
- Total Duration: 9261.90 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 63.32 tok/s
- TTFT: 594.12 ms
- Total Duration: 12513.32 ms

## Delta (B - A)
- Throughput Δ: +20.57 tok/s
- TTFT Δ: +94.48 ms (positive = Agent B faster TTFT)
