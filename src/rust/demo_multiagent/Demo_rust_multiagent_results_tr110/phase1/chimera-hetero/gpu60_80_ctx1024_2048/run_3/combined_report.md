# Rust Multi-Agent Report - Run 3

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 13.57s
- Sequential Estimate: 17.44s
- Speedup: 1.29x
- Efficiency: 64.3% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=60, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 101.88 tok/s
- TTFT: 216.84 ms
- Total Duration: 3879.59 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 100.67 tok/s
- TTFT: 7009.09 ms
- Total Duration: 13565.23 ms

## Delta (B - A)
- Throughput Δ: -1.22 tok/s
- TTFT Δ: -6792.25 ms (positive = Agent B faster TTFT)
