# Rust Multi-Agent Report – Run 5

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 107.58s
- Sequential Estimate: 154.92s
- Speedup: 1.44x
- Efficiency: 72.0% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 44.86 tok/s
- TTFT: 355.54 ms
- Total Duration: 107583.75 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 12.13 tok/s
- TTFT: 195.63 ms
- Total Duration: 47333.98 ms

## Delta (B - A)
- Throughput Δ: -32.73 tok/s
- TTFT Δ: +159.91 ms (positive = Agent B faster TTFT)
