# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 13.64s
- Sequential Estimate: 25.18s
- Speedup: 1.85x
- Efficiency: 92.3% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.98 tok/s
- TTFT: 770.53 ms
- Total Duration: 11546.76 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 52.62 tok/s
- TTFT: 603.49 ms
- Total Duration: 13636.68 ms

## Delta (B - A)
- Throughput Δ: +11.64 tok/s
- TTFT Δ: +167.04 ms (positive = Agent B faster TTFT)
