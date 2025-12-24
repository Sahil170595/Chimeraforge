# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 12.37s
- Sequential Estimate: 22.56s
- Speedup: 1.82x
- Efficiency: 91.2% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 42.66 tok/s
- TTFT: 682.80 ms
- Total Duration: 10194.60 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 56.83 tok/s
- TTFT: 584.55 ms
- Total Duration: 12366.81 ms

## Delta (B - A)
- Throughput Δ: +14.17 tok/s
- TTFT Δ: +98.25 ms (positive = Agent B faster TTFT)
