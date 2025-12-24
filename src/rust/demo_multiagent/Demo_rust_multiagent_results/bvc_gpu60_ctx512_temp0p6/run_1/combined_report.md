# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 19.40s
- Sequential Estimate: 30.21s
- Speedup: 1.56x
- Efficiency: 77.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 97.18 tok/s
- TTFT: 15077.01 ms
- Total Duration: 19400.00 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11434
- Config: num_gpu=60, num_ctx=512, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 98.25 tok/s
- TTFT: 4394.36 ms
- Total Duration: 10807.72 ms

## Delta (B - A)
- Throughput Δ: +1.07 tok/s
- TTFT Δ: +10682.65 ms (positive = Agent B faster TTFT)
