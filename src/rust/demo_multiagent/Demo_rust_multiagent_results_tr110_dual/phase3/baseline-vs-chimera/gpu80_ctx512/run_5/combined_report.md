# Rust Multi-Agent Report - Run 5

## Scenario
- Type: baseline_vs_chimera
- Concurrent Wall Time: 11.92s
- Sequential Estimate: 21.17s
- Speedup: 1.78x
- Efficiency: 88.8% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Baseline Collector)
- Base URL: http://127.0.0.1:11434
- Config: Ollama defaults
- Throughput: 41.12 tok/s
- TTFT: 315.56 ms
- Total Duration: 9249.95 ms

## Agent B (Chimera Insight)
- Base URL: http://127.0.0.1:11435
- Config: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
- Throughput: 56.76 tok/s
- TTFT: 311.00 ms
- Total Duration: 11915.86 ms

## Delta (B - A)
- Throughput Δ: +15.64 tok/s
- TTFT Δ: +4.56 ms (positive = Agent B faster TTFT)
