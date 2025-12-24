# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 14.83s
- Sequential Estimate: 18.58s
- Speedup: 1.25x
- Efficiency: 62.6% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 99.59 tok/s
- TTFT: 255.64 ms
- Total Duration: 3741.86 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 97.63 tok/s
- TTFT: 8313.38 ms
- Total Duration: 14833.89 ms

## Delta (B - A)
- Throughput Δ: -1.97 tok/s
- TTFT Δ: -8057.74 ms (positive = Agent B faster TTFT)
