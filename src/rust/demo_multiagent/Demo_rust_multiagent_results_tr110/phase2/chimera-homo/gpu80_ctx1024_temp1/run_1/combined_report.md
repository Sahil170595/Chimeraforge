# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 10.65s
- Sequential Estimate: 14.73s
- Speedup: 1.38x
- Efficiency: 69.1% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 99.88 tok/s
- TTFT: 226.09 ms
- Total Duration: 4072.88 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.20 tok/s
- TTFT: 4102.22 ms
- Total Duration: 10654.34 ms

## Delta (B - A)
- Throughput Δ: +0.32 tok/s
- TTFT Δ: -3876.13 ms (positive = Agent B faster TTFT)
