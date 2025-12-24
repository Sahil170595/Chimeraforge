# Rust Multi-Agent Report - Run 1

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 12.53s
- Sequential Estimate: 22.93s
- Speedup: 1.83x
- Efficiency: 91.5% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://localhost:11434
- Config: Ollama defaults
- Throughput: 42.47 tok/s
- TTFT: 647.75 ms
- Total Duration: 10402.46 ms

## Agent B (Chimera Insight)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 55.99 tok/s
- TTFT: 571.21 ms
- Total Duration: 12528.48 ms

## Delta (B - A)
- Throughput Δ: +13.52 tok/s
- TTFT Δ: +76.54 ms (positive = Agent B faster TTFT)
