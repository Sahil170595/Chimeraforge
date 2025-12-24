# Rust Multi-Agent Report - Run 3

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 19.04s
- Sequential Estimate: 27.74s
- Speedup: 1.46x
- Efficiency: 72.9% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 97.26 tok/s
- TTFT: 4310.19 ms
- Total Duration: 8700.21 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11434
- Config: num_gpu=60, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 99.34 tok/s
- TTFT: 12360.22 ms
- Total Duration: 19034.94 ms

## Delta (B - A)
- Throughput Δ: +2.08 tok/s
- TTFT Δ: -8050.03 ms (positive = Agent B faster TTFT)
