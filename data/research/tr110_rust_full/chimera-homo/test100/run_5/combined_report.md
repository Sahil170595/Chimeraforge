# Rust Multi-Agent Report - Run 5

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 59.08s
- Sequential Estimate: 117.88s
- Speedup: 2.00x
- Efficiency: 99.8% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.6, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.96 tok/s
- TTFT: 596.58 ms
- Total Duration: 58771.15 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=0.6, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.46 tok/s
- TTFT: 660.73 ms
- Total Duration: 59043.88 ms

## Delta (B - A)
- Throughput Δ: +0.50 tok/s
- TTFT Δ: -64.16 ms (positive = Agent B faster TTFT)
