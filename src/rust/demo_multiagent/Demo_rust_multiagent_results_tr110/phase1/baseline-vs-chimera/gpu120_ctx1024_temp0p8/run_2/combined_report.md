# Rust Multi-Agent Report - Run 2

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 18.17s
- Sequential Estimate: 26.23s
- Speedup: 1.44x
- Efficiency: 72.2% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 99.16 tok/s
- TTFT: 3616.46 ms
- Total Duration: 8055.93 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11434
- Config: num_gpu=120, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 99.97 tok/s
- TTFT: 11622.90 ms
- Total Duration: 18169.19 ms

## Delta (B - A)
- Throughput Δ: +0.82 tok/s
- TTFT Δ: -8006.44 ms (positive = Agent B faster TTFT)
