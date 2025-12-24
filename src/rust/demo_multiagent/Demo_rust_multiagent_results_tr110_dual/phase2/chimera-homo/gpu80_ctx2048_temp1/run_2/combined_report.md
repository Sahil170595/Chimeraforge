# Rust Multi-Agent Report - Run 2

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 11.56s
- Sequential Estimate: 19.94s
- Speedup: 1.72x
- Efficiency: 86.2% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.93 tok/s
- TTFT: 219.87 ms
- Total Duration: 8376.20 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 60.35 tok/s
- TTFT: 369.81 ms
- Total Duration: 11563.74 ms

## Delta (B - A)
- Throughput Δ: +18.42 tok/s
- TTFT Δ: -149.94 ms (positive = Agent B faster TTFT)
