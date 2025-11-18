# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 46.83s
- Sequential Estimate: 46.83s
- Speedup: 1.00x
- Efficiency: 50.0% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 109.03 tok/s
- TTFT: 562.18 ms
- Total Duration: 22920.07 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 108.04 tok/s
- TTFT: 598.54 ms
- Total Duration: 23852.81 ms

## Delta (B - A)
- Throughput Δ: -0.99 tok/s
- TTFT Δ: -36.36 ms (positive = Agent B faster TTFT)
