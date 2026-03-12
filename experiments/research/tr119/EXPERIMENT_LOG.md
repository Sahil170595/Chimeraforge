# TR119 Experiment Log

## 2025-12-13

- Initial TR119 infrastructure scaffolded (mirrors TR118 depth)
- Benchmark runner (`run_benchmark.py`) with resource telemetry integration
- Cost/energy analysis pipeline (`analyze_results.py`) with multi-tier cost model
- Report generator (`generate_report.py`) with cost/energy tables
- Artifact utilities (`artifact_utils.py`) for cost/energy calculations
- Dockerfile and requirements.txt for reproducibility

## Next Steps

- [ ] Replace `_dummy_benchmark` in `run_benchmark.py` with real TR118-style inference calls
- [ ] Add cloud pricing fetcher (AWS/Azure/GCP APIs)
- [ ] Add carbon footprint calculator
- [ ] Add TCO calculator script
- [ ] Add validation script (`validate_cost_energy.py`) for cost model accuracy
- [ ] Add smoke.yaml and matrix.yaml config variants
- [ ] Run first end-to-end benchmark with real backends

