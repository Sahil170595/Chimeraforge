# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 5.36s
- Sequential Estimate: 7.64s
- Speedup: 1.43x
- Efficiency: 71.3% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 95.18 tok/s
- TTFT: 938.74 ms
- Total Duration: 5358.88 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 47.84 tok/s
- TTFT: 670.91 ms
- Total Duration: 2282.43 ms

## Delta (B - A)
- Throughput Δ: -47.34 tok/s
- TTFT Δ: +267.83 ms (positive = Agent B faster TTFT)
