# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 47.70s
- Sequential Estimate: 47.70s
- Speedup: 1.00x
- Efficiency: 50.0% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 106.29 tok/s
- TTFT: 573.31 ms
- Total Duration: 25448.81 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 108.24 tok/s
- TTFT: 594.62 ms
- Total Duration: 22218.05 ms

## Delta (B - A)
- Throughput Δ: +1.94 tok/s
- TTFT Δ: -21.31 ms (positive = Agent B faster TTFT)
