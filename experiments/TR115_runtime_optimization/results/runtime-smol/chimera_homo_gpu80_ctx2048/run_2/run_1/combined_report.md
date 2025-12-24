# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 12.75s
- Sequential Estimate: 23.71s
- Speedup: 1.86x
- Efficiency: 93.0% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.50 tok/s
- TTFT: 642.60 ms
- Total Duration: 10960.08 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=2048, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 53.57 tok/s
- TTFT: 580.01 ms
- Total Duration: 12751.45 ms

## Delta (B - A)
- Throughput Δ: +11.06 tok/s
- TTFT Δ: +62.58 ms (positive = Agent B faster TTFT)
