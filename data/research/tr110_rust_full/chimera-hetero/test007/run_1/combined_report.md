# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 53.35s
- Sequential Estimate: 100.32s
- Speedup: 1.88x
- Efficiency: 94.0% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=60, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 51.47 tok/s
- TTFT: 2928.29 ms
- Total Duration: 53306.82 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 48.41 tok/s
- TTFT: 754.88 ms
- Total Duration: 46949.25 ms

## Delta (B - A)
- Throughput Δ: -3.06 tok/s
- TTFT Δ: +2173.41 ms (positive = Agent B faster TTFT)
