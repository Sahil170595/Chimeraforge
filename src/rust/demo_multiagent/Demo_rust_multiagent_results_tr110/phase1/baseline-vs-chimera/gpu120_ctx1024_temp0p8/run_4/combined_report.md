# Rust Multi-Agent Report - Run 4

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 14.17s
- Sequential Estimate: 20.93s
- Speedup: 1.48x
- Efficiency: 73.9% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 99.77 tok/s
- TTFT: 10166.15 ms
- Total Duration: 14167.32 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11434
- Config: num_gpu=120, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.65 tok/s
- TTFT: 212.23 ms
- Total Duration: 6764.40 ms

## Delta (B - A)
- Throughput Δ: +0.88 tok/s
- TTFT Δ: +9953.91 ms (positive = Agent B faster TTFT)
