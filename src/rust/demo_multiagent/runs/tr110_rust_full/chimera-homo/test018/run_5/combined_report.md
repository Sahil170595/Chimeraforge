# Rust Multi-Agent Report - Run 5

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 55.00s
- Sequential Estimate: 109.83s
- Speedup: 2.00x
- Efficiency: 99.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=120, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.91 tok/s
- TTFT: 615.36 ms
- Total Duration: 54798.58 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=120, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.17 tok/s
- TTFT: 688.58 ms
- Total Duration: 54955.20 ms

## Delta (B - A)
- Throughput Δ: +0.27 tok/s
- TTFT Δ: -73.21 ms (positive = Agent B faster TTFT)
