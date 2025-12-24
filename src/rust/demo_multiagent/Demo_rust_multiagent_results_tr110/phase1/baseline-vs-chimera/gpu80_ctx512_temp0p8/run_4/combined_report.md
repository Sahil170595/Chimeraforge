# Rust Multi-Agent Report - Run 4

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 18.13s
- Sequential Estimate: 26.48s
- Speedup: 1.46x
- Efficiency: 73.0% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 99.21 tok/s
- TTFT: 3623.90 ms
- Total Duration: 8350.14 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 99.98 tok/s
- TTFT: 12055.20 ms
- Total Duration: 18132.12 ms

## Delta (B - A)
- Throughput Δ: +0.77 tok/s
- TTFT Δ: -8431.29 ms (positive = Agent B faster TTFT)
