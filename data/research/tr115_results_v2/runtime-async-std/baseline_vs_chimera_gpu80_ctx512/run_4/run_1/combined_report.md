# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 47.14s
- Sequential Estimate: 47.13s
- Speedup: 1.00x
- Efficiency: 50.0% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 106.63 tok/s
- TTFT: 571.06 ms
- Total Duration: 24647.40 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 108.20 tok/s
- TTFT: 594.14 ms
- Total Duration: 22436.91 ms

## Delta (B - A)
- Throughput Δ: +1.57 tok/s
- TTFT Δ: -23.07 ms (positive = Agent B faster TTFT)
