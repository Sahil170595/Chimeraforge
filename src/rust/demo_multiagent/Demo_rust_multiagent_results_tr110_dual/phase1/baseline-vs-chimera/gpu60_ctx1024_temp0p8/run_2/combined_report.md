# Rust Multi-Agent Report - Run 2

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 13.48s
- Sequential Estimate: 24.51s
- Speedup: 1.82x
- Efficiency: 90.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://127.0.0.1:11434
- Config: Ollama defaults
- Throughput: 41.41 tok/s
- TTFT: 233.94 ms
- Total Duration: 11034.95 ms

## Agent B (Chimera Insight)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=60, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 52.99 tok/s
- TTFT: 316.43 ms
- Total Duration: 13476.16 ms

## Delta (B - A)
- Throughput Δ: +11.58 tok/s
- TTFT Δ: -82.49 ms (positive = Agent B faster TTFT)
