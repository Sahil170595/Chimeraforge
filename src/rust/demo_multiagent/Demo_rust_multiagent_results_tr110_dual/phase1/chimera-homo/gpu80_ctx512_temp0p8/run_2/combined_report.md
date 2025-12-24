# Rust Multi-Agent Report - Run 2

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 11.79s
- Sequential Estimate: 21.51s
- Speedup: 1.82x
- Efficiency: 91.2% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.85 tok/s
- TTFT: 287.72 ms
- Total Duration: 9722.94 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 53.78 tok/s
- TTFT: 337.14 ms
- Total Duration: 11791.41 ms

## Delta (B - A)
- Throughput Δ: +11.93 tok/s
- TTFT Δ: -49.41 ms (positive = Agent B faster TTFT)
