# TR112_v2 Rust vs Python Sweep Summary

- Total configurations analysed: **36**
- Python: avg baseline **99.04 tok/s**, avg chimera **99.14 tok/s** (mean throughput delta +0.10%), peak **101.08 tok/s** at `gpu60_ctx512_temp0.8`
- Rust: avg baseline **98.76 tok/s**, avg chimera **98.90 tok/s** (mean throughput delta +0.14%), peak **99.50 tok/s** at `gpu80_ctx512_temp0.8`

## Top Configurations by Language

### Python
- `gpu60_ctx512_temp0.8` -> chimera **101.08 tok/s**, baseline **98.90 tok/s**, throughput delta +2.20%, TTFT delta +68.44%
- `gpu60_ctx512_temp0.6` -> chimera **99.38 tok/s**, baseline **99.43 tok/s**, throughput delta -0.05%, TTFT delta -4.11%
- `gpu80_ctx1024_temp0.6` -> chimera **99.25 tok/s**, baseline **99.22 tok/s**, throughput delta +0.03%, TTFT delta -18.59%
- `gpu60_ctx256_temp0.6` -> chimera **99.21 tok/s**, baseline **99.39 tok/s**, throughput delta -0.18%, TTFT delta -3.97%
- `gpu60_ctx256_temp0.8` -> chimera **99.21 tok/s**, baseline **98.92 tok/s**, throughput delta +0.29%, TTFT delta -7.15%

### Rust
- `gpu80_ctx512_temp0.8` -> chimera **99.50 tok/s**, baseline **99.31 tok/s**, throughput delta +0.19%, TTFT delta +2.14%
- `gpu80_ctx256_temp0.6` -> chimera **99.47 tok/s**, baseline **99.09 tok/s**, throughput delta +0.38%, TTFT delta -0.06%
- `gpu80_ctx256_temp0.8` -> chimera **99.43 tok/s**, baseline **98.87 tok/s**, throughput delta +0.57%, TTFT delta +9.07%
- `gpu120_ctx1024_temp0.8` -> chimera **99.41 tok/s**, baseline **99.23 tok/s**, throughput delta +0.19%, TTFT delta +8.73%
- `gpu80_ctx512_temp0.6` -> chimera **99.27 tok/s**, baseline **99.53 tok/s**, throughput delta -0.26%, TTFT delta +0.19%

Data source: `artifacts/rust_vs_python_sweep_summary.csv` (generated from `benchmarks/python/chimera_sweep` and `Demo_rust_agent_sweep`).
