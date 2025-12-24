# Rust Multi-Agent Report - Run 5

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 13.88s
- Sequential Estimate: 20.53s
- Speedup: 1.48x
- Efficiency: 73.9% (ideal = 2x speedup)
- Contention Detected: Yes

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 99.58 tok/s
- TTFT: 10147.22 ms
- Total Duration: 13881.29 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 100.78 tok/s
- TTFT: 210.61 ms
- Total Duration: 6643.87 ms

## Delta (B - A)
- Throughput Δ: +1.20 tok/s
- TTFT Δ: +9936.61 ms (positive = Agent B faster TTFT)
