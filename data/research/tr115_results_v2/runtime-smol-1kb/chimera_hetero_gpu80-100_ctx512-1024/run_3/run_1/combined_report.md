# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 59.00s
- Sequential Estimate: 116.32s
- Speedup: 1.97x
- Efficiency: 98.6% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.21 tok/s
- TTFT: 1070.40 ms
- Total Duration: 57281.49 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 43.25 tok/s
- TTFT: 1049.55 ms
- Total Duration: 58958.14 ms

## Delta (B - A)
- Throughput Δ: +2.04 tok/s
- TTFT Δ: +20.85 ms (positive = Agent B faster TTFT)
