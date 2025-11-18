# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 55.23s
- Sequential Estimate: 109.19s
- Speedup: 1.98x
- Efficiency: 98.8% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.77 tok/s
- TTFT: 656.91 ms
- Total Duration: 55220.38 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.22 tok/s
- TTFT: 819.52 ms
- Total Duration: 53941.74 ms

## Delta (B - A)
- Throughput Δ: -1.55 tok/s
- TTFT Δ: -162.61 ms (positive = Agent B faster TTFT)
