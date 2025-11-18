# Benchmarks Artifact Tree

The `benchmarks/` directory centralizes every large benchmark drop that used to
live at the repository root.

## Layout
- `python/chimera_sweep/` - 18-configuration sweep outputs backing TR112/TR114.
- `python/demo_agent_benchmark/` - targeted scenario runs used for demos/tests.
- `rust/quick_test/` - scratch space populated by
  `scripts/windows/benchmarks/run_quick_rust_test.ps1`.

Results follow a consistent structure (`run_*/data/metrics.json`,
`run_*/reports/`), so downstream scripts can glob by folder name instead of
relying on ad-hoc paths.
