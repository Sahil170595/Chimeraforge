# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 10.33s
- Sequential Estimate: 10.33s
- Speedup: 1.00x
- Efficiency: 50.0% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 122.74 tok/s
- TTFT: 795.81 ms
- Total Duration: 4065.44 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 121.73 tok/s
- TTFT: 580.17 ms
- Total Duration: 6260.24 ms

## Delta (B - A)
- Throughput Δ: -1.02 tok/s
- TTFT Δ: +215.63 ms (positive = Agent B faster TTFT)
