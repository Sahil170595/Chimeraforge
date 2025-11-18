# Rust Multi-Agent Report - Run 3

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 59.17s
- Sequential Estimate: 116.89s
- Speedup: 1.98x
- Efficiency: 98.8% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 41.82 tok/s
- TTFT: 855.51 ms
- Total Duration: 59134.87 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=60, num_ctx=512, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.19 tok/s
- TTFT: 661.71 ms
- Total Duration: 57695.07 ms

## Delta (B - A)
- Throughput Δ: -1.63 tok/s
- TTFT Δ: +193.79 ms (positive = Agent B faster TTFT)
