# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 12.45s
- Sequential Estimate: 22.28s
- Speedup: 1.79x
- Efficiency: 89.5% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 41.06 tok/s
- TTFT: 651.13 ms
- Total Duration: 9827.57 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 56.32 tok/s
- TTFT: 601.54 ms
- Total Duration: 12451.27 ms

## Delta (B - A)
- Throughput Δ: +15.26 tok/s
- TTFT Δ: +49.59 ms (positive = Agent B faster TTFT)
