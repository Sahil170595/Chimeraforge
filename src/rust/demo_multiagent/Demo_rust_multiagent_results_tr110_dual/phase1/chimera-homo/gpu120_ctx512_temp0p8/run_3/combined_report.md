# Rust Multi-Agent Report - Run 3

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 12.30s
- Sequential Estimate: 22.40s
- Speedup: 1.82x
- Efficiency: 91.1% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=120, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.05 tok/s
- TTFT: 262.82 ms
- Total Duration: 10101.60 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=120, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 53.37 tok/s
- TTFT: 303.43 ms
- Total Duration: 12301.52 ms

## Delta (B - A)
- Throughput Δ: +12.32 tok/s
- TTFT Δ: -40.61 ms (positive = Agent B faster TTFT)
