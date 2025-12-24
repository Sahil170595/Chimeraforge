# Rust Multi-Agent Report - Run 5

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 13.37s
- Sequential Estimate: 17.16s
- Speedup: 1.28x
- Efficiency: 64.2% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 101.64 tok/s
- TTFT: 210.81 ms
- Total Duration: 3793.82 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.09 tok/s
- TTFT: 7024.30 ms
- Total Duration: 13369.86 ms

## Delta (B - A)
- Throughput Δ: -1.55 tok/s
- TTFT Δ: -6813.49 ms (positive = Agent B faster TTFT)
