# Rust vs Python Sweep Summary

## Python Agent

- Configurations evaluated: 18
- Positive throughput configs: 7 (38.9%)
- Avg throughput delta: +0.095%
- Avg TTFT delta: -9.393%
- Best throughput config: gpu=60, ctx=512, temp=0.8 (+2.200% throughput, +68.4% TTFT)
  - Source: benchmarks/python/chimera_sweep\run_gpu60_ctx512_temp0p8

## Rust Agent

- Configurations evaluated: 18
- Positive throughput configs: 13 (72.2%)
- Avg throughput delta: +0.138%
- Avg TTFT delta: +2.117%
- Best throughput config: gpu=60, ctx=1024, temp=0.8 (+0.606% throughput, -0.5% TTFT)
  - Source: Demo_rust_agent\Demo_rust_agent_sweep\gpu60_ctx1024_temp0p8
