# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 14.38s
- Sequential Estimate: 22.13s
- Speedup: 1.54x
- Efficiency: 76.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=120, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 98.45 tok/s
- TTFT: 3577.11 ms
- Total Duration: 7744.45 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=120, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.53 tok/s
- TTFT: 7771.38 ms
- Total Duration: 14382.10 ms

## Delta (B - A)
- Throughput Δ: +2.07 tok/s
- TTFT Δ: -4194.27 ms (positive = Agent B faster TTFT)
