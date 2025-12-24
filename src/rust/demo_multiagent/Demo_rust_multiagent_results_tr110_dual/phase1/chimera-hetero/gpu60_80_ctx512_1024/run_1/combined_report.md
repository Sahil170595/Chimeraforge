# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 20.97s
- Sequential Estimate: 39.84s
- Speedup: 1.90x
- Efficiency: 95.0% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://127.0.0.1:11434
- Config: num_gpu=60, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 40.98 tok/s
- TTFT: 7980.27 ms
- Total Duration: 18881.71 ms

## Agent B (Chimera Agent B)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
- Throughput: 52.04 tok/s
- TTFT: 7977.54 ms
- Total Duration: 20962.91 ms

## Delta (B - A)
- Throughput Δ: +11.06 tok/s
- TTFT Δ: +2.73 ms (positive = Agent B faster TTFT)
