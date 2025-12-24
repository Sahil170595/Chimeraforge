# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 55.15s
- Sequential Estimate: 109.24s
- Speedup: 1.98x
- Efficiency: 99.0% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.38 tok/s
- TTFT: 767.40 ms
- Total Duration: 54073.59 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.97 tok/s
- TTFT: 880.52 ms
- Total Duration: 55120.66 ms

## Delta (B - A)
- Throughput Δ: +0.58 tok/s
- TTFT Δ: -113.11 ms (positive = Agent B faster TTFT)
