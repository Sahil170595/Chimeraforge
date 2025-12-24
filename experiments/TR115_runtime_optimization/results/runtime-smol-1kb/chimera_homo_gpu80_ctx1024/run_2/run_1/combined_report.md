# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 12.89s
- Sequential Estimate: 23.89s
- Speedup: 1.85x
- Efficiency: 92.6% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.96 tok/s
- TTFT: 924.07 ms
- Total Duration: 10995.06 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 54.61 tok/s
- TTFT: 674.55 ms
- Total Duration: 12889.97 ms

## Delta (B - A)
- Throughput Δ: +11.65 tok/s
- TTFT Δ: +249.52 ms (positive = Agent B faster TTFT)
