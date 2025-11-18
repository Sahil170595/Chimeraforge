# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 53.93s
- Sequential Estimate: 107.15s
- Speedup: 1.99x
- Efficiency: 99.4% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=60, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.52 tok/s
- TTFT: 620.24 ms
- Total Duration: 53197.50 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=2048, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.06 tok/s
- TTFT: 830.64 ms
- Total Duration: 53895.58 ms

## Delta (B - A)
- Throughput Δ: +0.53 tok/s
- TTFT Δ: -210.40 ms (positive = Agent B faster TTFT)
