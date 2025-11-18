# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 59.62s
- Sequential Estimate: 117.89s
- Speedup: 1.98x
- Efficiency: 98.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 42.12 tok/s
- TTFT: 724.76 ms
- Total Duration: 59580.75 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.56 tok/s
- TTFT: 859.95 ms
- Total Duration: 58230.41 ms

## Delta (B - A)
- Throughput Δ: -1.56 tok/s
- TTFT Δ: -135.19 ms (positive = Agent B faster TTFT)
