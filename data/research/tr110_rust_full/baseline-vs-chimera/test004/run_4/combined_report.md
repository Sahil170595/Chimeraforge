# Rust Multi-Agent Report - Run 4

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 57.29s
- Sequential Estimate: 113.91s
- Speedup: 1.99x
- Efficiency: 99.4% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 40.39 tok/s
- TTFT: 696.98 ms
- Total Duration: 56588.62 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=1024, temp=0.8, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 41.56 tok/s
- TTFT: 685.87 ms
- Total Duration: 57256.50 ms

## Delta (B - A)
- Throughput Δ: +1.16 tok/s
- TTFT Δ: +11.11 ms (positive = Agent B faster TTFT)
