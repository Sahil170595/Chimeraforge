# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 58.09s
- Sequential Estimate: 116.17s
- Speedup: 2.00x
- Efficiency: 100.0% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.76 tok/s
- TTFT: 772.16 ms
- Total Duration: 58052.28 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.91 tok/s
- TTFT: 817.67 ms
- Total Duration: 58046.62 ms

## Delta (B - A)
- Throughput Δ: +0.15 tok/s
- TTFT Δ: -45.51 ms (positive = Agent B faster TTFT)
