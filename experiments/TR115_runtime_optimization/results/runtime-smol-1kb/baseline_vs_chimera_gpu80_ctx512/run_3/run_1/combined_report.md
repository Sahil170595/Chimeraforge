# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 12.30s
- Sequential Estimate: 22.29s
- Speedup: 1.81x
- Efficiency: 90.6% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 42.38 tok/s
- TTFT: 931.04 ms
- Total Duration: 9982.77 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 57.84 tok/s
- TTFT: 659.19 ms
- Total Duration: 12303.81 ms

## Delta (B - A)
- Throughput Δ: +15.45 tok/s
- TTFT Δ: +271.85 ms (positive = Agent B faster TTFT)
