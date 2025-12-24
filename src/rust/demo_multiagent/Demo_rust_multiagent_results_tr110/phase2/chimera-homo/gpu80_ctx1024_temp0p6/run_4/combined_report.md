# Rust Multi-Agent Report - Run 4

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 4.77s
- Sequential Estimate: 5.85s
- Speedup: 1.23x
- Efficiency: 61.3% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.38 tok/s
- TTFT: 1112.65 ms
- Total Duration: 4769.42 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 104.27 tok/s
- TTFT: 215.13 ms
- Total Duration: 1079.85 ms

## Delta (B - A)
- Throughput Δ: +3.89 tok/s
- TTFT Δ: +897.52 ms (positive = Agent B faster TTFT)
