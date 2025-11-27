# Rust Multi-Agent Report – Run 2

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 62.37s
- Sequential Estimate: 115.37s
- Speedup: 1.85x
- Efficiency: 92.5% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 22.15 tok/s
- TTFT: 270.80 ms
- Total Duration: 52998.12 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 28.18 tok/s
- TTFT: 285.98 ms
- Total Duration: 62370.53 ms

## Delta (B - A)
- Throughput Δ: +6.03 tok/s
- TTFT Δ: -15.19 ms (positive = Agent B faster TTFT)
