# Rust Multi-Agent Report - Run 2

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 13.51s
- Sequential Estimate: 24.64s
- Speedup: 1.82x
- Efficiency: 91.2% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.61 tok/s
- TTFT: 262.87 ms
- Total Duration: 11129.90 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 53.53 tok/s
- TTFT: 315.70 ms
- Total Duration: 13511.24 ms

## Delta (B - A)
- Throughput Δ: +11.93 tok/s
- TTFT Δ: -52.82 ms (positive = Agent B faster TTFT)
