# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 15.91s
- Sequential Estimate: 22.97s
- Speedup: 1.44x
- Efficiency: 72.2% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=120, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.91 tok/s
- TTFT: 3476.35 ms
- Total Duration: 7062.88 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=140, num_ctx=2048, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 100.30 tok/s
- TTFT: 10267.98 ms
- Total Duration: 15904.82 ms

## Delta (B - A)
- Throughput Δ: -0.61 tok/s
- TTFT Δ: -6791.64 ms (positive = Agent B faster TTFT)
