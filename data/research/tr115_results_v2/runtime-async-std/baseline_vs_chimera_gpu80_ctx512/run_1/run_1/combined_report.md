# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 50.21s
- Sequential Estimate: 50.21s
- Speedup: 1.00x
- Efficiency: 50.0% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 106.36 tok/s
- TTFT: 2076.78 ms
- Total Duration: 25955.33 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 115.99 tok/s
- TTFT: 3107.86 ms
- Total Duration: 24218.93 ms

## Delta (B - A)
- Throughput Δ: +9.63 tok/s
- TTFT Δ: -1031.08 ms (positive = Agent B faster TTFT)
