# Rust Multi-Agent Report - Run 5

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 14.89s
- Sequential Estimate: 21.94s
- Speedup: 1.47x
- Efficiency: 73.7% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 99.08 tok/s
- TTFT: 11056.12 ms
- Total Duration: 14892.86 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11434
- Config: num_gpu=60, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.33 tok/s
- TTFT: 248.88 ms
- Total Duration: 7051.78 ms

## Delta (B - A)
- Throughput Δ: +1.25 tok/s
- TTFT Δ: +10807.24 ms (positive = Agent B faster TTFT)
