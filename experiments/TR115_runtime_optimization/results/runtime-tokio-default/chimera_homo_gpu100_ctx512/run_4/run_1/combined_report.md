# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 13.73s
- Sequential Estimate: 25.95s
- Speedup: 1.89x
- Efficiency: 94.5% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.73 tok/s
- TTFT: 675.08 ms
- Total Duration: 12222.65 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 48.60 tok/s
- TTFT: 604.76 ms
- Total Duration: 13726.30 ms

## Delta (B - A)
- Throughput Δ: +7.87 tok/s
- TTFT Δ: +70.32 ms (positive = Agent B faster TTFT)
