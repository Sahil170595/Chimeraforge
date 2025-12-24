# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 13.10s
- Sequential Estimate: 24.11s
- Speedup: 1.84x
- Efficiency: 92.0% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.84 tok/s
- TTFT: 702.35 ms
- Total Duration: 11008.53 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 52.59 tok/s
- TTFT: 595.91 ms
- Total Duration: 13097.47 ms

## Delta (B - A)
- Throughput Δ: +11.75 tok/s
- TTFT Δ: +106.45 ms (positive = Agent B faster TTFT)
