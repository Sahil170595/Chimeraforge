# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 19.85s
- Sequential Estimate: 19.85s
- Speedup: 1.00x
- Efficiency: 50.0% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 123.17 tok/s
- TTFT: 6348.46 ms
- Total Duration: 9659.98 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 120.77 tok/s
- TTFT: 4681.52 ms
- Total Duration: 10188.11 ms

## Delta (B - A)
- Throughput Δ: -2.39 tok/s
- TTFT Δ: +1666.95 ms (positive = Agent B faster TTFT)
