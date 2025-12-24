# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 12.38s
- Sequential Estimate: 22.87s
- Speedup: 1.85x
- Efficiency: 92.4% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.88 tok/s
- TTFT: 906.90 ms
- Total Duration: 10498.98 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 54.60 tok/s
- TTFT: 708.64 ms
- Total Duration: 12374.12 ms

## Delta (B - A)
- Throughput Δ: +11.73 tok/s
- TTFT Δ: +198.26 ms (positive = Agent B faster TTFT)
