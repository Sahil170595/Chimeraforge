# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 15.77s
- Sequential Estimate: 22.53s
- Speedup: 1.43x
- Efficiency: 71.4% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=60, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.31 tok/s
- TTFT: 3071.07 ms
- Total Duration: 6761.10 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 101.03 tok/s
- TTFT: 9806.95 ms
- Total Duration: 15765.78 ms

## Delta (B - A)
- Throughput Δ: +0.73 tok/s
- TTFT Δ: -6735.88 ms (positive = Agent B faster TTFT)
