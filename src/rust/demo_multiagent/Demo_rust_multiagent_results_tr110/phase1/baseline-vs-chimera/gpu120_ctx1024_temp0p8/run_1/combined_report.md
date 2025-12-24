# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 8.15s
- Sequential Estimate: 11.92s
- Speedup: 1.46x
- Efficiency: 73.2% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 100.57 tok/s
- TTFT: 219.16 ms
- Total Duration: 3778.80 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11434
- Config: num_gpu=120, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 99.82 tok/s
- TTFT: 7087.13 ms
- Total Duration: 8145.00 ms

## Delta (B - A)
- Throughput Δ: -0.75 tok/s
- TTFT Δ: -6867.97 ms (positive = Agent B faster TTFT)
