# Rust Multi-Agent Report – Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 56.27s
- Sequential Estimate: 109.39s
- Speedup: 1.94x
- Efficiency: 97.2% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 11.15 tok/s
- TTFT: 3805.54 ms
- Total Duration: 56265.69 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 22.28 tok/s
- TTFT: 3709.27 ms
- Total Duration: 53119.23 ms

## Delta (B - A)
- Throughput Δ: +11.13 tok/s
- TTFT Δ: +96.27 ms (positive = Agent B faster TTFT)
