# Rust Multi-Agent Report – Run 2

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 32.64s
- Sequential Estimate: 63.11s
- Speedup: 1.93x
- Efficiency: 96.7% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 29.15 tok/s
- TTFT: 429.12 ms
- Total Duration: 32643.35 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 26.01 tok/s
- TTFT: 279.51 ms
- Total Duration: 30464.94 ms

## Delta (B - A)
- Throughput Δ: -3.13 tok/s
- TTFT Δ: +149.62 ms (positive = Agent B faster TTFT)
