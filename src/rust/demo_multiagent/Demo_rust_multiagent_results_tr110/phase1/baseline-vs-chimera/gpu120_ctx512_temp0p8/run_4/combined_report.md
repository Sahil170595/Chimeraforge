# Rust Multi-Agent Report - Run 4

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 18.00s
- Sequential Estimate: 28.22s
- Speedup: 1.57x
- Efficiency: 78.4% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 99.57 tok/s
- TTFT: 13703.61 ms
- Total Duration: 18004.68 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11434
- Config: num_gpu=120, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 98.99 tok/s
- TTFT: 3539.89 ms
- Total Duration: 10217.53 ms

## Delta (B - A)
- Throughput Δ: -0.58 tok/s
- TTFT Δ: +10163.73 ms (positive = Agent B faster TTFT)
