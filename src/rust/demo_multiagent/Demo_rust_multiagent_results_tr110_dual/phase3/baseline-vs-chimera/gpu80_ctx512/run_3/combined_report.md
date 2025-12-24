# Rust Multi-Agent Report - Run 3

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 11.98s
- Sequential Estimate: 21.25s
- Speedup: 1.77x
- Efficiency: 88.7% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://127.0.0.1:11434
- Config: Ollama defaults
- Throughput: 41.02 tok/s
- TTFT: 276.75 ms
- Total Duration: 9270.86 ms

## Agent B (Chimera Insight)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 56.73 tok/s
- TTFT: 316.51 ms
- Total Duration: 11976.59 ms

## Delta (B - A)
- Throughput Δ: +15.71 tok/s
- TTFT Δ: -39.76 ms (positive = Agent B faster TTFT)
