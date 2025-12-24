# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 57.17s
- Sequential Estimate: 113.88s
- Speedup: 1.99x
- Efficiency: 99.6% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 39.90 tok/s
- TTFT: 705.17 ms
- Total Duration: 56696.43 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.06 tok/s
- TTFT: 885.14 ms
- Total Duration: 57144.35 ms

## Delta (B - A)
- Throughput Δ: +0.15 tok/s
- TTFT Δ: -179.97 ms (positive = Agent B faster TTFT)
