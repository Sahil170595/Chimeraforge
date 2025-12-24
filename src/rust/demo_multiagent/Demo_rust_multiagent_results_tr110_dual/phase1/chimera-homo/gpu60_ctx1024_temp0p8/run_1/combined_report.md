# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 11.94s
- Sequential Estimate: 20.95s
- Speedup: 1.75x
- Efficiency: 87.7% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=60, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.39 tok/s
- TTFT: 278.84 ms
- Total Duration: 9013.81 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=60, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 58.79 tok/s
- TTFT: 300.70 ms
- Total Duration: 11935.78 ms

## Delta (B - A)
- Throughput Δ: +17.40 tok/s
- TTFT Δ: -21.86 ms (positive = Agent B faster TTFT)
