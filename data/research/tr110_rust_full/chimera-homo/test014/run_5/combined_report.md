# Rust Multi-Agent Report - Run 5

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 55.16s
- Sequential Estimate: 110.04s
- Speedup: 2.00x
- Efficiency: 99.8% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=60, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.69 tok/s
- TTFT: 481.14 ms
- Total Duration: 54853.88 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=60, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.35 tok/s
- TTFT: 675.60 ms
- Total Duration: 55126.38 ms

## Delta (B - A)
- Throughput Δ: +0.66 tok/s
- TTFT Δ: -194.46 ms (positive = Agent B faster TTFT)
