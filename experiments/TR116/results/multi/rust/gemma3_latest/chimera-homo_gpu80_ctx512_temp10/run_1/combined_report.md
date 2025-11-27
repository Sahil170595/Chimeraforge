# Rust Multi-Agent Report – Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 56.31s
- Sequential Estimate: 111.61s
- Speedup: 1.98x
- Efficiency: 99.1% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 48.53 tok/s
- TTFT: 622.03 ms
- Total Duration: 56307.31 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.14 tok/s
- TTFT: 2185.33 ms
- Total Duration: 55300.42 ms

## Delta (B - A)
- Throughput Δ: -7.39 tok/s
- TTFT Δ: -1563.30 ms (positive = Agent B faster TTFT)
