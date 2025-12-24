# Rust Multi-Agent Report - Run 3

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 10.59s
- Sequential Estimate: 17.09s
- Speedup: 1.61x
- Efficiency: 80.7% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 99.96 tok/s
- TTFT: 6533.35 ms
- Total Duration: 10586.65 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 99.67 tok/s
- TTFT: 197.52 ms
- Total Duration: 6502.88 ms

## Delta (B - A)
- Throughput Δ: -0.29 tok/s
- TTFT Δ: +6335.83 ms (positive = Agent B faster TTFT)
