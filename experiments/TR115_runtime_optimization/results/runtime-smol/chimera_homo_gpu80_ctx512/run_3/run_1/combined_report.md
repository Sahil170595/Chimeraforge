# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 11.83s
- Sequential Estimate: 21.35s
- Speedup: 1.81x
- Efficiency: 90.3% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.75 tok/s
- TTFT: 663.04 ms
- Total Duration: 9524.93 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 58.24 tok/s
- TTFT: 589.28 ms
- Total Duration: 11826.08 ms

## Delta (B - A)
- Throughput Δ: +15.49 tok/s
- TTFT Δ: +73.75 ms (positive = Agent B faster TTFT)
