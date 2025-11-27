# Rust Multi-Agent Report – Run 2

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 47.98s
- Sequential Estimate: 93.46s
- Speedup: 1.95x
- Efficiency: 97.4% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 27.67 tok/s
- TTFT: 340.55 ms
- Total Duration: 47977.21 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 24.18 tok/s
- TTFT: 228.94 ms
- Total Duration: 45486.20 ms

## Delta (B - A)
- Throughput Δ: -3.49 tok/s
- TTFT Δ: +111.61 ms (positive = Agent B faster TTFT)
