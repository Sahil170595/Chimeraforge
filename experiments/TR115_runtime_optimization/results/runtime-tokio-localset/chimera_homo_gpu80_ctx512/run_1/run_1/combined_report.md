# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 11.41s
- Sequential Estimate: 15.73s
- Speedup: 1.38x
- Efficiency: 68.9% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 105.89 tok/s
- TTFT: 699.64 ms
- Total Duration: 4319.64 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 113.37 tok/s
- TTFT: 5486.80 ms
- Total Duration: 11405.91 ms

## Delta (B - A)
- Throughput Δ: +7.47 tok/s
- TTFT Δ: -4787.16 ms (positive = Agent B faster TTFT)
