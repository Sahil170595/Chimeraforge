# Rust Multi-Agent Report - Run 3

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 12.89s
- Sequential Estimate: 23.88s
- Speedup: 1.85x
- Efficiency: 92.6% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://127.0.0.1:11434
- Config: Ollama defaults
- Throughput: 41.18 tok/s
- TTFT: 276.29 ms
- Total Duration: 10986.88 ms

## Agent B (Chimera Insight)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=60, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 50.94 tok/s
- TTFT: 306.90 ms
- Total Duration: 12890.73 ms

## Delta (B - A)
- Throughput Δ: +9.76 tok/s
- TTFT Δ: -30.61 ms (positive = Agent B faster TTFT)
