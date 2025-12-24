# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 10.11s
- Sequential Estimate: 10.11s
- Speedup: 1.00x
- Efficiency: 50.0% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 122.27 tok/s
- TTFT: 848.17 ms
- Total Duration: 4166.65 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 121.05 tok/s
- TTFT: 588.59 ms
- Total Duration: 5942.95 ms

## Delta (B - A)
- Throughput Δ: -1.21 tok/s
- TTFT Δ: +259.59 ms (positive = Agent B faster TTFT)
