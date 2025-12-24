# Rust Multi-Agent Report - Run 2

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 13.81s
- Sequential Estimate: 25.12s
- Speedup: 1.82x
- Efficiency: 91.0% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=2048, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.82 tok/s
- TTFT: 203.97 ms
- Total Duration: 11313.58 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=2048, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 53.41 tok/s
- TTFT: 350.84 ms
- Total Duration: 13807.67 ms

## Delta (B - A)
- Throughput Δ: +11.59 tok/s
- TTFT Δ: -146.87 ms (positive = Agent B faster TTFT)
