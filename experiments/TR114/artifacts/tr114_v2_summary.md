# TR114_v2 Multi-Agent Summary (from tr110_rust_full runs)

- Total configurations: **27** across 4 scenarios.
- `baseline-vs-chimera` -> mean efficiency **97.37%**, peak **98.98%** (`test004`), lowest **91.60%** (`test005`), mean speedup **1.95x**
- `chimera-hetero` -> mean efficiency **98.79%**, peak **99.40%** (`test011`), lowest **97.90%** (`test007`), mean speedup **1.98x**
- `chimera-homo` -> mean efficiency **98.40%**, peak **99.36%** (`test018`), lowest **94.23%** (`test100`), mean speedup **1.97x**
- `chimera_homo` -> mean efficiency **99.03%**, peak **99.24%** (`test103`), lowest **98.82%** (`test104`), mean speedup **1.98x**

## Highest-Efficiency Configurations

- `chimera-hetero/test011` -> **99.40%**, speedup **1.988x**, throughput delta -0.46 tok/s (source: `Demo_rust_multiagent\runs\tr110_rust_full\chimera-hetero\test011\summary.json`)
- `chimera-homo/test018` -> **99.36%**, speedup **1.987x**, throughput delta +0.82 tok/s (source: `Demo_rust_multiagent\runs\tr110_rust_full\chimera-homo\test018\summary.json`)
- `chimera_homo/test103` -> **99.24%**, speedup **1.985x**, throughput delta +1.04 tok/s (source: `Demo_rust_multiagent\runs\tr110_rust_full\chimera_homo\test103\summary.json`)
- `chimera-homo/test014` -> **99.15%**, speedup **1.983x**, throughput delta +1.11 tok/s (source: `Demo_rust_multiagent\runs\tr110_rust_full\chimera-homo\test014\summary.json`)
- `chimera-homo/test200` -> **99.01%**, speedup **1.980x**, throughput delta -1.23 tok/s (source: `Demo_rust_multiagent\runs\tr110_rust_full\chimera-homo\test200\summary.json`)

Data source: `Demo_rust_multiagent/runs/tr110_rust_full/*/summary.json`.