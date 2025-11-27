# Rust Multi-Agent Report – Run 3

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 53.61s
- Sequential Estimate: 106.31s
- Speedup: 1.98x
- Efficiency: 99.1% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.88 tok/s
- TTFT: 577.42 ms
- Total Duration: 52695.54 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.99 tok/s
- TTFT: 317.57 ms
- Total Duration: 53609.83 ms

## Delta (B - A)
- Throughput Δ: +1.11 tok/s
- TTFT Δ: +259.85 ms (positive = Agent B faster TTFT)
