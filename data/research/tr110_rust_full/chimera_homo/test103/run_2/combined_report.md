# Rust Multi-Agent Report - Run 2

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 58.41s
- Sequential Estimate: 116.69s
- Speedup: 2.00x
- Efficiency: 99.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.6, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.99 tok/s
- TTFT: 662.37 ms
- Total Duration: 58213.70 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=0.6, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.14 tok/s
- TTFT: 670.64 ms
- Total Duration: 58325.92 ms

## Delta (B - A)
- Throughput Δ: +0.15 tok/s
- TTFT Δ: -8.27 ms (positive = Agent B faster TTFT)
