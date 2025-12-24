# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_hetero
- Concurrent Wall Time: 54.50s
- Sequential Estimate: 105.89s
- Speedup: 1.94x
- Efficiency: 97.2% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 40.83 tok/s
- TTFT: 659.58 ms
- Total Duration: 51384.76 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=100, num_ctx=1024, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 44.99 tok/s
- TTFT: 814.26 ms
- Total Duration: 54481.00 ms

## Delta (B - A)
- Throughput Δ: +4.16 tok/s
- TTFT Δ: -154.67 ms (positive = Agent B faster TTFT)
