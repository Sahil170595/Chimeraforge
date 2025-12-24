# Rust Multi-Agent Report - Run 4

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 10.54s
- Sequential Estimate: 14.87s
- Speedup: 1.41x
- Efficiency: 70.6% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 101.23 tok/s
- TTFT: 223.62 ms
- Total Duration: 4336.12 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 101.31 tok/s
- TTFT: 4365.48 ms
- Total Duration: 10538.28 ms

## Delta (B - A)
- Throughput Δ: +0.08 tok/s
- TTFT Δ: -4141.86 ms (positive = Agent B faster TTFT)
