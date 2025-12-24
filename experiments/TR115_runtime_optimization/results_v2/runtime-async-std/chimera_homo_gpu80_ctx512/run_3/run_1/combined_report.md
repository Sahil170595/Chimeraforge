# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 44.76s
- Sequential Estimate: 44.76s
- Speedup: 1.00x
- Efficiency: 50.0% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 108.37 tok/s
- TTFT: 553.07 ms
- Total Duration: 21827.75 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 108.44 tok/s
- TTFT: 588.85 ms
- Total Duration: 22868.28 ms

## Delta (B - A)
- Throughput Δ: +0.07 tok/s
- TTFT Δ: -35.78 ms (positive = Agent B faster TTFT)
