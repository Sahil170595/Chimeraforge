# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 53.11s
- Sequential Estimate: 99.18s
- Speedup: 1.87x
- Efficiency: 93.4% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 56.75 tok/s
- TTFT: 690.35 ms
- Total Duration: 46045.71 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 52.27 tok/s
- TTFT: 4676.26 ms
- Total Duration: 53091.21 ms

## Delta (B - A)
- Throughput Δ: -4.48 tok/s
- TTFT Δ: -3985.91 ms (positive = Agent B faster TTFT)
