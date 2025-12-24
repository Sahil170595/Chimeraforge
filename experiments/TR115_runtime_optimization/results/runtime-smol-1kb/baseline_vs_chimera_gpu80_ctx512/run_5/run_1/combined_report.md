# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 13.46s
- Sequential Estimate: 24.92s
- Speedup: 1.85x
- Efficiency: 92.5% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 42.31 tok/s
- TTFT: 835.82 ms
- Total Duration: 11458.08 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 53.82 tok/s
- TTFT: 757.12 ms
- Total Duration: 13463.18 ms

## Delta (B - A)
- Throughput Δ: +11.51 tok/s
- TTFT Δ: +78.70 ms (positive = Agent B faster TTFT)
