# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 11.95s
- Sequential Estimate: 21.78s
- Speedup: 1.82x
- Efficiency: 91.1% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.06 tok/s
- TTFT: 287.15 ms
- Total Duration: 9829.51 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 53.45 tok/s
- TTFT: 306.44 ms
- Total Duration: 11949.40 ms

## Delta (B - A)
- Throughput Δ: +12.39 tok/s
- TTFT Δ: -19.29 ms (positive = Agent B faster TTFT)
