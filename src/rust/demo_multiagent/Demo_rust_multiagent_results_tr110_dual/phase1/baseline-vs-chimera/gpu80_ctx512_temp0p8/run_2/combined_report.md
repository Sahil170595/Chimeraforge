# Rust Multi-Agent Report - Run 2

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 12.97s
- Sequential Estimate: 23.69s
- Speedup: 1.83x
- Efficiency: 91.3% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://127.0.0.1:11434
- Config: Ollama defaults
- Throughput: 42.03 tok/s
- TTFT: 209.41 ms
- Total Duration: 10719.74 ms

## Agent B (Chimera Insight)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 53.31 tok/s
- TTFT: 379.11 ms
- Total Duration: 12974.60 ms

## Delta (B - A)
- Throughput Δ: +11.28 tok/s
- TTFT Δ: -169.70 ms (positive = Agent B faster TTFT)
