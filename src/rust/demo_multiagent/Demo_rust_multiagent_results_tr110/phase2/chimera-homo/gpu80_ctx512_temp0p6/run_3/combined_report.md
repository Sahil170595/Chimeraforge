# Rust Multi-Agent Report - Run 3

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 11.12s
- Sequential Estimate: 15.73s
- Speedup: 1.41x
- Efficiency: 70.7% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.98 tok/s
- TTFT: 224.44 ms
- Total Duration: 4613.09 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 102.21 tok/s
- TTFT: 4643.41 ms
- Total Duration: 11115.39 ms

## Delta (B - A)
- Throughput Δ: +1.22 tok/s
- TTFT Δ: -4418.96 ms (positive = Agent B faster TTFT)
