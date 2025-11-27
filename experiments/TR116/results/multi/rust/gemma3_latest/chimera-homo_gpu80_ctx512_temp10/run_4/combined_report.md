# Rust Multi-Agent Report – Run 4

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 51.94s
- Sequential Estimate: 103.59s
- Speedup: 1.99x
- Efficiency: 99.7% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.44 tok/s
- TTFT: 598.86 ms
- Total Duration: 51938.48 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.18 tok/s
- TTFT: 435.83 ms
- Total Duration: 51654.21 ms

## Delta (B - A)
- Throughput Δ: -0.25 tok/s
- TTFT Δ: +163.04 ms (positive = Agent B faster TTFT)
