# Rust Multi-Agent Report - Run 3

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 14.93s
- Sequential Estimate: 21.96s
- Speedup: 1.47x
- Efficiency: 73.5% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 99.24 tok/s
- TTFT: 10458.33 ms
- Total Duration: 14929.06 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11434
- Config: num_gpu=120, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.54 tok/s
- TTFT: 201.89 ms
- Total Duration: 7029.73 ms

## Delta (B - A)
- Throughput Δ: +1.31 tok/s
- TTFT Δ: +10256.44 ms (positive = Agent B faster TTFT)
