# Rust Multi-Agent Report - Run 2

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 54.16s
- Sequential Estimate: 107.94s
- Speedup: 1.99x
- Efficiency: 99.7% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.77 tok/s
- TTFT: 674.69 ms
- Total Duration: 53750.84 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.18 tok/s
- TTFT: 615.57 ms
- Total Duration: 54117.45 ms

## Delta (B - A)
- Throughput Δ: +0.41 tok/s
- TTFT Δ: +59.12 ms (positive = Agent B faster TTFT)
