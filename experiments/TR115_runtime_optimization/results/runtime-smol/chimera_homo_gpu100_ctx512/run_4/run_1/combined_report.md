# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 11.71s
- Sequential Estimate: 20.84s
- Speedup: 1.78x
- Efficiency: 89.0% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.65 tok/s
- TTFT: 688.81 ms
- Total Duration: 9127.68 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 60.63 tok/s
- TTFT: 564.42 ms
- Total Duration: 11710.35 ms

## Delta (B - A)
- Throughput Δ: +17.98 tok/s
- TTFT Δ: +124.40 ms (positive = Agent B faster TTFT)
