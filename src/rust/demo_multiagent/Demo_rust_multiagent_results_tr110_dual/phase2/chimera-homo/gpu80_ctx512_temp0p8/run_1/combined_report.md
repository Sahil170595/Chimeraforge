# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 11.53s
- Sequential Estimate: 20.46s
- Speedup: 1.77x
- Efficiency: 88.7% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.42 tok/s
- TTFT: 300.65 ms
- Total Duration: 8928.09 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 57.01 tok/s
- TTFT: 307.74 ms
- Total Duration: 11530.97 ms

## Delta (B - A)
- Throughput Δ: +15.58 tok/s
- TTFT Δ: -7.09 ms (positive = Agent B faster TTFT)
