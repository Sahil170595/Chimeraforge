# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 12.37s
- Sequential Estimate: 21.81s
- Speedup: 1.76x
- Efficiency: 88.2% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://127.0.0.1:11434
- Config: Ollama defaults
- Throughput: 41.20 tok/s
- TTFT: 311.44 ms
- Total Duration: 9446.07 ms

## Agent B (Chimera Insight)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 57.60 tok/s
- TTFT: 320.72 ms
- Total Duration: 12366.51 ms

## Delta (B - A)
- Throughput Δ: +16.40 tok/s
- TTFT Δ: -9.28 ms (positive = Agent B faster TTFT)
