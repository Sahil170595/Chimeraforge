# Rust Multi-Agent Report – Run 4

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 31.02s
- Sequential Estimate: 61.61s
- Speedup: 1.99x
- Efficiency: 99.3% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 26.48 tok/s
- TTFT: 379.01 ms
- Total Duration: 31022.16 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 25.97 tok/s
- TTFT: 284.67 ms
- Total Duration: 30589.53 ms

## Delta (B - A)
- Throughput Δ: -0.51 tok/s
- TTFT Δ: +94.34 ms (positive = Agent B faster TTFT)
