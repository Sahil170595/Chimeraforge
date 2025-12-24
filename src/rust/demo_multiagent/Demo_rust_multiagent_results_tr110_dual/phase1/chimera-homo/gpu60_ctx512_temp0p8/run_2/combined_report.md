# Rust Multi-Agent Report - Run 2

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 13.01s
- Sequential Estimate: 23.80s
- Speedup: 1.83x
- Efficiency: 91.4% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=60, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 41.40 tok/s
- TTFT: 298.63 ms
- Total Duration: 10788.00 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=60, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 53.30 tok/s
- TTFT: 349.83 ms
- Total Duration: 13013.65 ms

## Delta (B - A)
- Throughput Δ: +11.90 tok/s
- TTFT Δ: -51.20 ms (positive = Agent B faster TTFT)
