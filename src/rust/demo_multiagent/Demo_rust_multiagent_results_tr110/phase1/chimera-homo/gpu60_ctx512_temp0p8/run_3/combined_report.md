# Rust Multi-Agent Report - Run 3

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 10.96s
- Sequential Estimate: 15.17s
- Speedup: 1.38x
- Efficiency: 69.2% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=60, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.74 tok/s
- TTFT: 188.44 ms
- Total Duration: 4210.16 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=60, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.34 tok/s
- TTFT: 4240.84 ms
- Total Duration: 10964.13 ms

## Delta (B - A)
- Throughput Δ: -0.40 tok/s
- TTFT Δ: -4052.41 ms (positive = Agent B faster TTFT)
