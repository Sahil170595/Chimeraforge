# Rust Multi-Agent Report - Run 4

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 16.62s
- Sequential Estimate: 26.51s
- Speedup: 1.60x
- Efficiency: 79.8% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 100.55 tok/s
- TTFT: 13194.92 ms
- Total Duration: 16617.88 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.52 tok/s
- TTFT: 3449.30 ms
- Total Duration: 9896.45 ms

## Delta (B - A)
- Throughput Δ: -0.03 tok/s
- TTFT Δ: +9745.62 ms (positive = Agent B faster TTFT)
