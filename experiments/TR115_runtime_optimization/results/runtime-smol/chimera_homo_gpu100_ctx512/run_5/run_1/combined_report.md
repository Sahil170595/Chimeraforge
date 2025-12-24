# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 12.49s
- Sequential Estimate: 23.05s
- Speedup: 1.85x
- Efficiency: 92.3% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.66 tok/s
- TTFT: 599.44 ms
- Total Duration: 10559.86 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 54.52 tok/s
- TTFT: 566.37 ms
- Total Duration: 12485.31 ms

## Delta (B - A)
- Throughput Δ: +11.85 tok/s
- TTFT Δ: +33.07 ms (positive = Agent B faster TTFT)
