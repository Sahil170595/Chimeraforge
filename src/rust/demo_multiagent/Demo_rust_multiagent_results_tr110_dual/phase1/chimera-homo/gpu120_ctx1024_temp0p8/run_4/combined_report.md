# Rust Multi-Agent Report - Run 4

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 12.37s
- Sequential Estimate: 22.50s
- Speedup: 1.82x
- Efficiency: 91.0% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=120, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.20 tok/s
- TTFT: 304.52 ms
- Total Duration: 10135.51 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=120, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 53.94 tok/s
- TTFT: 293.96 ms
- Total Duration: 12365.86 ms

## Delta (B - A)
- Throughput Δ: +12.74 tok/s
- TTFT Δ: +10.56 ms (positive = Agent B faster TTFT)
