# Rust Multi-Agent Report - Run 2

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 58.00s
- Sequential Estimate: 115.56s
- Speedup: 1.99x
- Efficiency: 99.6% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=120, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.99 tok/s
- TTFT: 665.61 ms
- Total Duration: 57490.43 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=120, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.48 tok/s
- TTFT: 675.49 ms
- Total Duration: 57920.46 ms

## Delta (B - A)
- Throughput Δ: +0.50 tok/s
- TTFT Δ: -9.87 ms (positive = Agent B faster TTFT)
