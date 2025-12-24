# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 126.27s
- Sequential Estimate: 126.26s
- Speedup: 1.00x
- Efficiency: 50.0% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.15 tok/s
- TTFT: 6426.18 ms
- Total Duration: 70391.35 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.40 tok/s
- TTFT: 858.86 ms
- Total Duration: 55806.63 ms

## Delta (B - A)
- Throughput Δ: -0.75 tok/s
- TTFT Δ: +5567.32 ms (positive = Agent B faster TTFT)
