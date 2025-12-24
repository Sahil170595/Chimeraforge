# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 45.18s
- Sequential Estimate: 45.18s
- Speedup: 1.00x
- Efficiency: 50.0% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 108.41 tok/s
- TTFT: 545.17 ms
- Total Duration: 24149.21 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 107.63 tok/s
- TTFT: 596.98 ms
- Total Duration: 20969.48 ms

## Delta (B - A)
- Throughput Δ: -0.78 tok/s
- TTFT Δ: -51.81 ms (positive = Agent B faster TTFT)
