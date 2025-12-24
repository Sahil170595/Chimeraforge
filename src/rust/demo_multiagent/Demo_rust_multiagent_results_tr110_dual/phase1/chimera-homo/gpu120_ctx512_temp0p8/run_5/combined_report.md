# Rust Multi-Agent Report - Run 5

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 13.47s
- Sequential Estimate: 24.89s
- Speedup: 1.85x
- Efficiency: 92.4% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=120, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.12 tok/s
- TTFT: 284.54 ms
- Total Duration: 11416.61 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=120, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 51.66 tok/s
- TTFT: 314.12 ms
- Total Duration: 13474.43 ms

## Delta (B - A)
- Throughput Δ: +10.54 tok/s
- TTFT Δ: -29.58 ms (positive = Agent B faster TTFT)
