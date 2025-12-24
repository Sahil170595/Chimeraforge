# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 18.81s
- Sequential Estimate: 29.08s
- Speedup: 1.55x
- Efficiency: 77.3% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 97.74 tok/s
- TTFT: 14255.06 ms
- Total Duration: 18806.76 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 97.58 tok/s
- TTFT: 3973.96 ms
- Total Duration: 10273.50 ms

## Delta (B - A)
- Throughput Δ: -0.16 tok/s
- TTFT Δ: +10281.10 ms (positive = Agent B faster TTFT)
