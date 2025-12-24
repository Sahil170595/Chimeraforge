# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 20.50s
- Sequential Estimate: 38.66s
- Speedup: 1.89x
- Efficiency: 94.3% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=120, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 40.98 tok/s
- TTFT: 8185.21 ms
- Total Duration: 18159.26 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=140, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 53.78 tok/s
- TTFT: 8141.68 ms
- Total Duration: 20495.88 ms

## Delta (B - A)
- Throughput Δ: +12.80 tok/s
- TTFT Δ: +43.53 ms (positive = Agent B faster TTFT)
