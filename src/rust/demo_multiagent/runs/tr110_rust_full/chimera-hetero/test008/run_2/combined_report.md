# Rust Multi-Agent Report - Run 2

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 56.69s
- Sequential Estimate: 110.22s
- Speedup: 1.94x
- Efficiency: 97.2% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=60, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.90 tok/s
- TTFT: 503.73 ms
- Total Duration: 53502.47 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=2048, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 45.19 tok/s
- TTFT: 661.38 ms
- Total Duration: 56655.20 ms

## Delta (B - A)
- Throughput Δ: +4.29 tok/s
- TTFT Δ: -157.65 ms (positive = Agent B faster TTFT)
