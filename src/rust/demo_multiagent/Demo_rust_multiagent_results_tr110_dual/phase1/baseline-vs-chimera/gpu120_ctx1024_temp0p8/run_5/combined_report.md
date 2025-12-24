# Rust Multi-Agent Report - Run 5

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 12.15s
- Sequential Estimate: 21.82s
- Speedup: 1.80x
- Efficiency: 89.8% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://127.0.0.1:11434
- Config: Ollama defaults
- Throughput: 41.00 tok/s
- TTFT: 259.62 ms
- Total Duration: 9678.26 ms

## Agent B (Chimera Insight)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=120, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 55.31 tok/s
- TTFT: 295.77 ms
- Total Duration: 12145.30 ms

## Delta (B - A)
- Throughput Δ: +14.31 tok/s
- TTFT Δ: -36.15 ms (positive = Agent B faster TTFT)
