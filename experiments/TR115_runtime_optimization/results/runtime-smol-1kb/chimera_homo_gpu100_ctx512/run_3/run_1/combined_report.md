# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 11.90s
- Sequential Estimate: 21.99s
- Speedup: 1.85x
- Efficiency: 92.4% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.34 tok/s
- TTFT: 884.14 ms
- Total Duration: 10090.26 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 54.82 tok/s
- TTFT: 657.88 ms
- Total Duration: 11903.04 ms

## Delta (B - A)
- Throughput Δ: +12.49 tok/s
- TTFT Δ: +226.27 ms (positive = Agent B faster TTFT)
