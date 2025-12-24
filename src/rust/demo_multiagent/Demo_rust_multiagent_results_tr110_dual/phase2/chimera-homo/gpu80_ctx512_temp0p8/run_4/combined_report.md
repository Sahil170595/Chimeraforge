# Rust Multi-Agent Report - Run 4

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 12.73s
- Sequential Estimate: 23.45s
- Speedup: 1.84x
- Efficiency: 92.1% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 40.77 tok/s
- TTFT: 289.65 ms
- Total Duration: 10724.78 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 51.65 tok/s
- TTFT: 279.69 ms
- Total Duration: 12725.69 ms

## Delta (B - A)
- Throughput Δ: +10.87 tok/s
- TTFT Δ: +9.96 ms (positive = Agent B faster TTFT)
