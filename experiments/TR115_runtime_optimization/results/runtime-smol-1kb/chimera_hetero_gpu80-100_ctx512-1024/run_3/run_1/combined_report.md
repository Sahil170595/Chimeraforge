# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 12.89s
- Sequential Estimate: 24.40s
- Speedup: 1.89x
- Efficiency: 94.6% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 43.02 tok/s
- TTFT: 1038.78 ms
- Total Duration: 11510.08 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 52.88 tok/s
- TTFT: 683.33 ms
- Total Duration: 12889.78 ms

## Delta (B - A)
- Throughput Δ: +9.86 tok/s
- TTFT Δ: +355.45 ms (positive = Agent B faster TTFT)
