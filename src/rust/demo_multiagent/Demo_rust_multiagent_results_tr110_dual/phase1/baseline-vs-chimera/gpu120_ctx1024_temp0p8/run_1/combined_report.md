# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 13.48s
- Sequential Estimate: 24.78s
- Speedup: 1.84x
- Efficiency: 91.9% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://127.0.0.1:11434
- Config: Ollama defaults
- Throughput: 41.04 tok/s
- TTFT: 269.00 ms
- Total Duration: 11303.05 ms

## Agent B (Chimera Insight)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=120, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 52.33 tok/s
- TTFT: 304.96 ms
- Total Duration: 13474.48 ms

## Delta (B - A)
- Throughput Δ: +11.29 tok/s
- TTFT Δ: -35.96 ms (positive = Agent B faster TTFT)
