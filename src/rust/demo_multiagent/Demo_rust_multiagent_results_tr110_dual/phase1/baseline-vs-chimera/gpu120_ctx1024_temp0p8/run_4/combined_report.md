# Rust Multi-Agent Report - Run 4

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 13.17s
- Sequential Estimate: 24.93s
- Speedup: 1.89x
- Efficiency: 94.7% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://127.0.0.1:11434
- Config: Ollama defaults
- Throughput: 41.25 tok/s
- TTFT: 240.82 ms
- Total Duration: 11766.39 ms

## Agent B (Chimera Insight)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=120, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 48.24 tok/s
- TTFT: 300.29 ms
- Total Duration: 13168.44 ms

## Delta (B - A)
- Throughput Δ: +6.98 tok/s
- TTFT Δ: -59.47 ms (positive = Agent B faster TTFT)
