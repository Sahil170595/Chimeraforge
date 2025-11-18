# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 103.01s
- Sequential Estimate: 103.01s
- Speedup: 1.00x
- Efficiency: 50.0% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 108.60 tok/s
- TTFT: 610.82 ms
- Total Duration: 82411.05 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 108.46 tok/s
- TTFT: 584.78 ms
- Total Duration: 20532.29 ms

## Delta (B - A)
- Throughput Δ: -0.14 tok/s
- TTFT Δ: +26.04 ms (positive = Agent B faster TTFT)
