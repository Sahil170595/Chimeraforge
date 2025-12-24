# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 52.64s
- Sequential Estimate: 104.03s
- Speedup: 1.98x
- Efficiency: 98.8% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.80 tok/s
- TTFT: 495.17 ms
- Total Duration: 52625.55 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.19 tok/s
- TTFT: 812.90 ms
- Total Duration: 51371.45 ms

## Delta (B - A)
- Throughput Δ: -1.61 tok/s
- TTFT Δ: -317.73 ms (positive = Agent B faster TTFT)
