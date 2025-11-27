# Rust Multi-Agent Report – Run 2

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 77.22s
- Sequential Estimate: 131.56s
- Speedup: 1.70x
- Efficiency: 85.2% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 23.89 tok/s
- TTFT: 293.45 ms
- Total Duration: 54341.20 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 54.58 tok/s
- TTFT: 174.04 ms
- Total Duration: 77222.94 ms

## Delta (B - A)
- Throughput Δ: +30.69 tok/s
- TTFT Δ: +119.41 ms (positive = Agent B faster TTFT)
