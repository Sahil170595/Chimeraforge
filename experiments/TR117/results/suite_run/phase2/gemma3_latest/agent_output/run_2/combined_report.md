# Rust Multi-Agent Report – Run 2

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 53.62s
- Sequential Estimate: 106.57s
- Speedup: 1.99x
- Efficiency: 99.4% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 38.62 tok/s
- TTFT: 505.93 ms
- Total Duration: 52952.48 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 39.46 tok/s
- TTFT: 495.72 ms
- Total Duration: 53617.34 ms

## Delta (B - A)
- Throughput Δ: +0.84 tok/s
- TTFT Δ: +10.21 ms (positive = Agent B faster TTFT)
