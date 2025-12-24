# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 11.68s
- Sequential Estimate: 21.27s
- Speedup: 1.82x
- Efficiency: 91.1% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.52 tok/s
- TTFT: 698.88 ms
- Total Duration: 9596.52 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 57.11 tok/s
- TTFT: 575.49 ms
- Total Duration: 11676.48 ms

## Delta (B - A)
- Throughput Δ: +14.59 tok/s
- TTFT Δ: +123.39 ms (positive = Agent B faster TTFT)
