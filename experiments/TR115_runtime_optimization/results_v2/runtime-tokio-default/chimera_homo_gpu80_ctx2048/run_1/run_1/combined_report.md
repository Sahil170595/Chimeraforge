# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 55.51s
- Sequential Estimate: 110.24s
- Speedup: 1.99x
- Efficiency: 99.3% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.17 tok/s
- TTFT: 682.81 ms
- Total Duration: 55494.78 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.93 tok/s
- TTFT: 841.09 ms
- Total Duration: 54709.71 ms

## Delta (B - A)
- Throughput Δ: -1.23 tok/s
- TTFT Δ: -158.27 ms (positive = Agent B faster TTFT)
