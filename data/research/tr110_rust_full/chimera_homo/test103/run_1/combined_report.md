# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 60.10s
- Sequential Estimate: 119.17s
- Speedup: 1.98x
- Efficiency: 99.1% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.6, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.51 tok/s
- TTFT: 3387.91 ms
- Total Duration: 59032.97 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=0.6, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.01 tok/s
- TTFT: 3551.66 ms
- Total Duration: 60067.37 ms

## Delta (B - A)
- Throughput Δ: +1.50 tok/s
- TTFT Δ: -163.75 ms (positive = Agent B faster TTFT)
