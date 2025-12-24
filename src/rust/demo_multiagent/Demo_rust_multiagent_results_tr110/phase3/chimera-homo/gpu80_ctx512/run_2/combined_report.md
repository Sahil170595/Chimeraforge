# Rust Multi-Agent Report - Run 2

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 10.75s
- Sequential Estimate: 17.49s
- Speedup: 1.63x
- Efficiency: 81.3% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 101.68 tok/s
- TTFT: 6767.58 ms
- Total Duration: 10751.93 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 101.79 tok/s
- TTFT: 200.95 ms
- Total Duration: 6738.64 ms

## Delta (B - A)
- Throughput Δ: +0.12 tok/s
- TTFT Δ: +6566.62 ms (positive = Agent B faster TTFT)
