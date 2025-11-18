# Rust Multi-Agent Report - Run 3

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 58.77s
- Sequential Estimate: 117.50s
- Speedup: 2.00x
- Efficiency: 100.0% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 40.85 tok/s
- TTFT: 860.16 ms
- Total Duration: 58742.65 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=120, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.86 tok/s
- TTFT: 650.12 ms
- Total Duration: 58700.17 ms

## Delta (B - A)
- Throughput Δ: +0.01 tok/s
- TTFT Δ: +210.04 ms (positive = Agent B faster TTFT)
