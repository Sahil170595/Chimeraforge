# Rust Multi-Agent Report - Run 2

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 53.85s
- Sequential Estimate: 106.01s
- Speedup: 1.97x
- Efficiency: 98.4% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=60, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 43.34 tok/s
- TTFT: 674.41 ms
- Total Duration: 53814.62 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.19 tok/s
- TTFT: 671.25 ms
- Total Duration: 52131.55 ms

## Delta (B - A)
- Throughput Δ: -2.15 tok/s
- TTFT Δ: +3.16 ms (positive = Agent B faster TTFT)
