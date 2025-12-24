# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 5.53s
- Sequential Estimate: 7.50s
- Speedup: 1.36x
- Efficiency: 67.9% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 93.96 tok/s
- TTFT: 753.71 ms
- Total Duration: 5526.26 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 47.31 tok/s
- TTFT: 615.39 ms
- Total Duration: 1977.92 ms

## Delta (B - A)
- Throughput Δ: -46.64 tok/s
- TTFT Δ: +138.32 ms (positive = Agent B faster TTFT)
