# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 56.38s
- Sequential Estimate: 111.85s
- Speedup: 1.98x
- Efficiency: 99.2% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.42 tok/s
- TTFT: 835.93 ms
- Total Duration: 55703.73 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.31 tok/s
- TTFT: 831.56 ms
- Total Duration: 54802.03 ms

## Delta (B - A)
- Throughput Δ: -1.12 tok/s
- TTFT Δ: +4.37 ms (positive = Agent B faster TTFT)
