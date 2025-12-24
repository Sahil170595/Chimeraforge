# Rust Multi-Agent Report - Run 1

## Scenario
- Type: chimera_homo
- Concurrent Wall Time: 11.89s
- Sequential Estimate: 21.11s
- Speedup: 1.78x
- Efficiency: 88.8% (ideal = 2x speedup)
- Contention Detected: No

## Agent A (Chimera Agent A)
- Base URL: http://localhost:11434
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 42.85 tok/s
- TTFT: 882.58 ms
- Total Duration: 9224.02 ms

## Agent B (Chimera Agent B)
- Base URL: http://localhost:11435
- Config: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
- Throughput: 60.60 tok/s
- TTFT: 688.98 ms
- Total Duration: 11890.80 ms

## Delta (B - A)
- Throughput Δ: +17.75 tok/s
- TTFT Δ: +193.60 ms (positive = Agent B faster TTFT)
