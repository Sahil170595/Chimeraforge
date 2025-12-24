# Rust Multi-Agent Report - Run 5

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 10.48s
- Sequential Estimate: 14.33s
- Speedup: 1.37x
- Efficiency: 68.4% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 102.68 tok/s
- TTFT: 194.08 ms
- Total Duration: 3849.73 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 101.59 tok/s
- TTFT: 3877.10 ms
- Total Duration: 10478.18 ms

## Delta (B - A)
- Throughput Δ: -1.09 tok/s
- TTFT Δ: -3683.02 ms (positive = Agent B faster TTFT)
