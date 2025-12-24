# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 10.16s
- Sequential Estimate: 14.86s
- Speedup: 1.46x
- Efficiency: 73.1% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 110.10 tok/s
- TTFT: 733.90 ms
- Total Duration: 4702.03 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 118.78 tok/s
- TTFT: 4746.21 ms
- Total Duration: 10157.38 ms

## Delta (B - A)
- Throughput Δ: +8.69 tok/s
- TTFT Δ: -4012.31 ms (positive = Agent B faster TTFT)
