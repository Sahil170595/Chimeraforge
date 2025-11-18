# Rust Multi-Agent Report - Run 3

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 59.94s
- Sequential Estimate: 115.89s
- Speedup: 1.93x
- Efficiency: 96.7% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 44.32 tok/s
- TTFT: 837.70 ms
- Total Duration: 59916.15 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=60, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.24 tok/s
- TTFT: 668.10 ms
- Total Duration: 55921.43 ms

## Delta (B - A)
- Throughput Δ: -4.08 tok/s
- TTFT Δ: +169.60 ms (positive = Agent B faster TTFT)
