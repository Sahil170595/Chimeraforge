# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 56.59s
- Sequential Estimate: 112.27s
- Speedup: 1.98x
- Efficiency: 99.2% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.41 tok/s
- TTFT: 631.73 ms
- Total Duration: 55653.71 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.25 tok/s
- TTFT: 825.46 ms
- Total Duration: 56553.03 ms

## Delta (B - A)
- Throughput Δ: +0.84 tok/s
- TTFT Δ: -193.73 ms (positive = Agent B faster TTFT)
