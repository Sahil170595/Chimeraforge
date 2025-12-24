# Rust Multi-Agent Report - Run 3

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 12.74s
- Sequential Estimate: 22.31s
- Speedup: 1.75x
- Efficiency: 87.6% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://127.0.0.1:11434
- Config: Ollama defaults
- Throughput: 42.02 tok/s
- TTFT: 209.75 ms
- Total Duration: 9571.75 ms

## Agent B (Chimera Insight)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=60, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 58.28 tok/s
- TTFT: 355.58 ms
- Total Duration: 12740.53 ms

## Delta (B - A)
- Throughput Δ: +16.25 tok/s
- TTFT Δ: -145.84 ms (positive = Agent B faster TTFT)
