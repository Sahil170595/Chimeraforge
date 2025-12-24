# Rust Multi-Agent Report - Run 4

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 10.24s
- Sequential Estimate: 16.75s
- Speedup: 1.63x
- Efficiency: 81.7% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=60, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.82 tok/s
- TTFT: 6529.25 ms
- Total Duration: 10242.52 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=60, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.22 tok/s
- TTFT: 201.03 ms
- Total Duration: 6502.93 ms

## Delta (B - A)
- Throughput Δ: -0.60 tok/s
- TTFT Δ: +6328.23 ms (positive = Agent B faster TTFT)
