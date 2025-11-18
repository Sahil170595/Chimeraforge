# Rust Multi-Agent Report - Run 3

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 56.29s
- Sequential Estimate: 111.52s
- Speedup: 1.98x
- Efficiency: 99.1% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=120, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.82 tok/s
- TTFT: 647.32 ms
- Total Duration: 55206.27 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=120, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.16 tok/s
- TTFT: 661.91 ms
- Total Duration: 56262.56 ms

## Delta (B - A)
- Throughput Δ: +1.33 tok/s
- TTFT Δ: -14.59 ms (positive = Agent B faster TTFT)
