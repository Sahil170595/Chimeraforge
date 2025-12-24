# Rust Multi-Agent Report - Run 5

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 12.47s
- Sequential Estimate: 22.85s
- Speedup: 1.83x
- Efficiency: 91.6% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://127.0.0.1:11434
- Config: Ollama defaults
- Throughput: 40.94 tok/s
- TTFT: 254.23 ms
- Total Duration: 10377.06 ms

## Agent B (Chimera Insight)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=60, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 52.17 tok/s
- TTFT: 294.94 ms
- Total Duration: 12469.50 ms

## Delta (B - A)
- Throughput Δ: +11.22 tok/s
- TTFT Δ: -40.71 ms (positive = Agent B faster TTFT)
