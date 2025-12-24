# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 12.05s
- Sequential Estimate: 22.48s
- Speedup: 1.87x
- Efficiency: 93.3% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 42.64 tok/s
- TTFT: 689.73 ms
- Total Duration: 10434.25 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 53.37 tok/s
- TTFT: 582.85 ms
- Total Duration: 12045.35 ms

## Delta (B - A)
- Throughput Δ: +10.74 tok/s
- TTFT Δ: +106.87 ms (positive = Agent B faster TTFT)
