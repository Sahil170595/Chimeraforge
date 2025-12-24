# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 56.50s
- Sequential Estimate: 112.83s
- Speedup: 2.00x
- Efficiency: 99.8% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.37 tok/s
- TTFT: 777.58 ms
- Total Duration: 56469.20 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.88 tok/s
- TTFT: 817.58 ms
- Total Duration: 56299.44 ms

## Delta (B - A)
- Throughput Δ: -0.48 tok/s
- TTFT Δ: -40.00 ms (positive = Agent B faster TTFT)
