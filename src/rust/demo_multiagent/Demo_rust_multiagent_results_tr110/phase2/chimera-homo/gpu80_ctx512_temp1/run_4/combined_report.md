# Rust Multi-Agent Report - Run 4

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 10.61s
- Sequential Estimate: 17.03s
- Speedup: 1.60x
- Efficiency: 80.2% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 99.41 tok/s
- TTFT: 6444.34 ms
- Total Duration: 10613.06 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.16 tok/s
- TTFT: 202.28 ms
- Total Duration: 6418.68 ms

## Delta (B - A)
- Throughput Δ: +0.75 tok/s
- TTFT Δ: +6242.06 ms (positive = Agent B faster TTFT)
