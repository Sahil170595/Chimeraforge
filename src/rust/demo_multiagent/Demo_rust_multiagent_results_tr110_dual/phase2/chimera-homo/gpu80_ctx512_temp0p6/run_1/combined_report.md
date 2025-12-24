# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 12.81s
- Sequential Estimate: 22.99s
- Speedup: 1.80x
- Efficiency: 89.8% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=512, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.29 tok/s
- TTFT: 638.26 ms
- Total Duration: 10187.94 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=512, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 56.09 tok/s
- TTFT: 635.20 ms
- Total Duration: 12803.28 ms

## Delta (B - A)
- Throughput Δ: +14.80 tok/s
- TTFT Δ: +3.06 ms (positive = Agent B faster TTFT)
