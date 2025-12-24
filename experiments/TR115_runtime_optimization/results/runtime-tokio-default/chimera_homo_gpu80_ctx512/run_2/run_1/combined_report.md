# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 5.28s
- Sequential Estimate: 7.39s
- Speedup: 1.40x
- Efficiency: 69.9% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 92.06 tok/s
- TTFT: 783.19 ms
- Total Duration: 5283.14 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 48.37 tok/s
- TTFT: 623.32 ms
- Total Duration: 2103.91 ms

## Delta (B - A)
- Throughput Δ: -43.69 tok/s
- TTFT Δ: +159.87 ms (positive = Agent B faster TTFT)
