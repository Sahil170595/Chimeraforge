# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 53.55s
- Sequential Estimate: 101.72s
- Speedup: 1.90x
- Efficiency: 95.0% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 48.47 tok/s
- TTFT: 920.52 ms
- Total Duration: 48143.06 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 50.16 tok/s
- TTFT: 3241.85 ms
- Total Duration: 53518.37 ms

## Delta (B - A)
- Throughput Δ: +1.69 tok/s
- TTFT Δ: -2321.34 ms (positive = Agent B faster TTFT)
