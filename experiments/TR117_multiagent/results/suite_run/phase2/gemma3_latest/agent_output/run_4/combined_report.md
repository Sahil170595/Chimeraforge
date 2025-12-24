# Rust Multi-Agent Report – Run 4

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 57.05s
- Sequential Estimate: 110.75s
- Speedup: 1.94x
- Efficiency: 97.1% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 38.41 tok/s
- TTFT: 500.09 ms
- Total Duration: 53707.23 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.21 tok/s
- TTFT: 522.71 ms
- Total Duration: 57044.52 ms

## Delta (B - A)
- Throughput Δ: +3.80 tok/s
- TTFT Δ: -22.62 ms (positive = Agent B faster TTFT)
