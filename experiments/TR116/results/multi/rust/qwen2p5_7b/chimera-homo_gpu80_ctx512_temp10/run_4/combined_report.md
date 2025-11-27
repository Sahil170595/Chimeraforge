# Rust Multi-Agent Report – Run 4

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 59.68s
- Sequential Estimate: 109.57s
- Speedup: 1.84x
- Efficiency: 91.8% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 30.37 tok/s
- TTFT: 318.95 ms
- Total Duration: 59676.54 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 24.19 tok/s
- TTFT: 229.96 ms
- Total Duration: 49889.01 ms

## Delta (B - A)
- Throughput Δ: -6.18 tok/s
- TTFT Δ: +88.98 ms (positive = Agent B faster TTFT)
