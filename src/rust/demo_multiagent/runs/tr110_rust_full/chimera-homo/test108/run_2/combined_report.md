# Rust Multi-Agent Report - Run 2

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 55.98s
- Sequential Estimate: 111.02s
- Speedup: 1.98x
- Efficiency: 99.2% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.03 tok/s
- TTFT: 646.17 ms
- Total Duration: 55959.20 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.94 tok/s
- TTFT: 661.63 ms
- Total Duration: 55012.10 ms

## Delta (B - A)
- Throughput Δ: -1.09 tok/s
- TTFT Δ: -15.46 ms (positive = Agent B faster TTFT)
