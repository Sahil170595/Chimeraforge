# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 15.21s
- Sequential Estimate: 19.62s
- Speedup: 1.29x
- Efficiency: 64.5% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 98.43 tok/s
- TTFT: 239.22 ms
- Total Duration: 4406.46 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 97.96 tok/s
- TTFT: 8485.28 ms
- Total Duration: 15211.35 ms

## Delta (B - A)
- Throughput Δ: -0.47 tok/s
- TTFT Δ: -8246.06 ms (positive = Agent B faster TTFT)
