# Rust Multi-Agent Report - Run 4

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 12.98s
- Sequential Estimate: 23.48s
- Speedup: 1.81x
- Efficiency: 90.5% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://127.0.0.1:11434
- Config: Ollama defaults
- Throughput: 40.94 tok/s
- TTFT: 257.76 ms
- Total Duration: 10503.52 ms

## Agent B (Chimera Insight)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=60, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 53.71 tok/s
- TTFT: 321.98 ms
- Total Duration: 12976.09 ms

## Delta (B - A)
- Throughput Δ: +12.77 tok/s
- TTFT Δ: -64.21 ms (positive = Agent B faster TTFT)
