# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 11.42s
- Sequential Estimate: 11.42s
- Speedup: 1.00x
- Efficiency: 50.0% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 123.15 tok/s
- TTFT: 904.09 ms
- Total Duration: 4857.47 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 121.02 tok/s
- TTFT: 581.56 ms
- Total Duration: 6560.92 ms

## Delta (B - A)
- Throughput Δ: -2.13 tok/s
- TTFT Δ: +322.53 ms (positive = Agent B faster TTFT)
