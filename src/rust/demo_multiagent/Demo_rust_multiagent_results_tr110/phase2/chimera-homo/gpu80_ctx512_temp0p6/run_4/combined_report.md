# Rust Multi-Agent Report - Run 4

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 10.77s
- Sequential Estimate: 15.13s
- Speedup: 1.40x
- Efficiency: 70.2% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.60 tok/s
- TTFT: 201.94 ms
- Total Duration: 4359.69 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 101.32 tok/s
- TTFT: 4390.08 ms
- Total Duration: 10770.66 ms

## Delta (B - A)
- Throughput Δ: +0.72 tok/s
- TTFT Δ: -4188.14 ms (positive = Agent B faster TTFT)
