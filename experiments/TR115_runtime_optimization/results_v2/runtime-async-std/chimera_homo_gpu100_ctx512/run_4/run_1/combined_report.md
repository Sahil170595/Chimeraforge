# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 118.37s
- Sequential Estimate: 118.37s
- Speedup: 1.00x
- Efficiency: 50.0% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.03 tok/s
- TTFT: 823.03 ms
- Total Duration: 60210.24 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.71 tok/s
- TTFT: 858.19 ms
- Total Duration: 58089.60 ms

## Delta (B - A)
- Throughput Δ: +0.69 tok/s
- TTFT Δ: -35.16 ms (positive = Agent B faster TTFT)
