# Rust Multi-Agent Report - Run 2

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 13.87s
- Sequential Estimate: 20.11s
- Speedup: 1.45x
- Efficiency: 72.5% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 99.84 tok/s
- TTFT: 9413.49 ms
- Total Duration: 13872.11 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 101.56 tok/s
- TTFT: 208.02 ms
- Total Duration: 6236.24 ms

## Delta (B - A)
- Throughput Δ: +1.72 tok/s
- TTFT Δ: +9205.46 ms (positive = Agent B faster TTFT)
