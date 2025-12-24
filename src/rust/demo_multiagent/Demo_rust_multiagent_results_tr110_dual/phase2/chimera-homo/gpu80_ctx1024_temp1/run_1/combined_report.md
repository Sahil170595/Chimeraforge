# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 12.88s
- Sequential Estimate: 22.33s
- Speedup: 1.73x
- Efficiency: 86.7% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 42.30 tok/s
- TTFT: 208.32 ms
- Total Duration: 9455.52 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 59.68 tok/s
- TTFT: 362.89 ms
- Total Duration: 12873.12 ms

## Delta (B - A)
- Throughput Δ: +17.37 tok/s
- TTFT Δ: -154.57 ms (positive = Agent B faster TTFT)
