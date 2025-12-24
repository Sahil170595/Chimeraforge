# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 12.48s
- Sequential Estimate: 23.41s
- Speedup: 1.88x
- Efficiency: 93.8% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.41 tok/s
- TTFT: 668.59 ms
- Total Duration: 10934.91 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 52.45 tok/s
- TTFT: 572.50 ms
- Total Duration: 12477.35 ms

## Delta (B - A)
- Throughput Δ: +10.04 tok/s
- TTFT Δ: +96.09 ms (positive = Agent B faster TTFT)
