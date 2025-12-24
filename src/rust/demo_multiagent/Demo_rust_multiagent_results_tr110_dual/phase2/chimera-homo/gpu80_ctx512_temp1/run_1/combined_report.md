# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 12.62s
- Sequential Estimate: 22.13s
- Speedup: 1.75x
- Efficiency: 87.7% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.14 tok/s
- TTFT: 302.45 ms
- Total Duration: 9519.81 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 58.02 tok/s
- TTFT: 326.01 ms
- Total Duration: 12614.39 ms

## Delta (B - A)
- Throughput Δ: +16.88 tok/s
- TTFT Δ: -23.56 ms (positive = Agent B faster TTFT)
