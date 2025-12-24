# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 19.15s
- Sequential Estimate: 29.93s
- Speedup: 1.56x
- Efficiency: 78.1% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 97.83 tok/s
- TTFT: 14423.72 ms
- Total Duration: 19149.19 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11434
- Config: num_gpu=120, num_ctx=512, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 97.45 tok/s
- TTFT: 3990.11 ms
- Total Duration: 10781.91 ms

## Delta (B - A)
- Throughput Δ: -0.38 tok/s
- TTFT Δ: +10433.61 ms (positive = Agent B faster TTFT)
