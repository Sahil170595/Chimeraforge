# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 61.94s
- Sequential Estimate: 120.66s
- Speedup: 1.95x
- Efficiency: 97.4% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 39.57 tok/s
- TTFT: 551.66 ms
- Total Duration: 58699.04 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.90 tok/s
- TTFT: 889.97 ms
- Total Duration: 61913.37 ms

## Delta (B - A)
- Throughput Δ: +3.33 tok/s
- TTFT Δ: -338.30 ms (positive = Agent B faster TTFT)
