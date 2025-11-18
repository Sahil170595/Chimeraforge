# Rust Multi-Agent Report - Run 3

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 56.11s
- Sequential Estimate: 110.71s
- Speedup: 1.97x
- Efficiency: 98.6% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 40.72 tok/s
- TTFT: 833.01 ms
- Total Duration: 54570.61 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=120, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.75 tok/s
- TTFT: 645.43 ms
- Total Duration: 56082.23 ms

## Delta (B - A)
- Throughput Δ: +2.03 tok/s
- TTFT Δ: +187.58 ms (positive = Agent B faster TTFT)
