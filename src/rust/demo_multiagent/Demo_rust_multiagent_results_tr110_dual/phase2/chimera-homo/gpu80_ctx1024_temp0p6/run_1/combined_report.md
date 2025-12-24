# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 12.72s
- Sequential Estimate: 23.23s
- Speedup: 1.83x
- Efficiency: 91.3% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.29 tok/s
- TTFT: 266.25 ms
- Total Duration: 10509.34 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=1024, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 53.08 tok/s
- TTFT: 318.71 ms
- Total Duration: 12718.34 ms

## Delta (B - A)
- Throughput Δ: +11.79 tok/s
- TTFT Δ: -52.46 ms (positive = Agent B faster TTFT)
