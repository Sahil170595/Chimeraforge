# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 5.18s
- Sequential Estimate: 7.25s
- Speedup: 1.40x
- Efficiency: 70.0% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 91.35 tok/s
- TTFT: 715.92 ms
- Total Duration: 5179.44 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 46.61 tok/s
- TTFT: 607.75 ms
- Total Duration: 2075.52 ms

## Delta (B - A)
- Throughput Δ: -44.74 tok/s
- TTFT Δ: +108.17 ms (positive = Agent B faster TTFT)
