# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 12.97s
- Sequential Estimate: 24.16s
- Speedup: 1.86x
- Efficiency: 93.2% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.77 tok/s
- TTFT: 687.01 ms
- Total Duration: 11194.64 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 50.70 tok/s
- TTFT: 603.90 ms
- Total Duration: 12969.92 ms

## Delta (B - A)
- Throughput Δ: +9.93 tok/s
- TTFT Δ: +83.11 ms (positive = Agent B faster TTFT)
