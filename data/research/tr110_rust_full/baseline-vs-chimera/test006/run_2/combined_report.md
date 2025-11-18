# Rust Multi-Agent Report - Run 2

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 58.08s
- Sequential Estimate: 115.55s
- Speedup: 1.99x
- Efficiency: 99.5% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 40.49 tok/s
- TTFT: 669.40 ms
- Total Duration: 57434.64 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=120, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.68 tok/s
- TTFT: 667.73 ms
- Total Duration: 58052.95 ms

## Delta (B - A)
- Throughput Δ: +1.20 tok/s
- TTFT Δ: +1.67 ms (positive = Agent B faster TTFT)
