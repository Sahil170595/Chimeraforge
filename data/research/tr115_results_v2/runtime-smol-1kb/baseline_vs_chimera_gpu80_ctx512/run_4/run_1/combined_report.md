# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 58.55s
- Sequential Estimate: 113.97s
- Speedup: 1.95x
- Efficiency: 97.3% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 44.35 tok/s
- TTFT: 993.84 ms
- Total Duration: 58531.82 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.68 tok/s
- TTFT: 1067.31 ms
- Total Duration: 55405.69 ms

## Delta (B - A)
- Throughput Δ: -3.67 tok/s
- TTFT Δ: -73.47 ms (positive = Agent B faster TTFT)
