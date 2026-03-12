# TR119: Cost & Energy Analysis

**Status:** Infrastructure Complete (at parity with TR118 depth)  
**Target:** Week of 2025-12-16  
**Depends On:** TR117, TR118

## Research Question

What is the true total cost of ownership (TCO) for each backend, including energy consumption and cloud pricing variability?

## Scope

- Multi-tier cost model (spot, on-demand, reserved, on-prem)
- Energy measurement (Joules/token, carbon footprint)
- Cloud provider comparison (AWS, Azure, GCP)
- Power profiling (GPU wattage, thermal throttling)
- TCO calculator for 1M req/day workload

## Key Gaps from TR117

- Oversimplified cost model ($0.035/hr flat rate)
- No energy consumption measurement
- Missing cloud provider generalization
- No carbon footprint analysis

## Infrastructure (Frontier Lab Quality)

TR119 is now fully built out with **frontier lab quality** capabilities matching TR117 Tier 3 standards:

### Core Scripts
- `run_experiment.py` - End-to-end orchestrator (benchmark → analyze → statistical analysis → visualize → report)
- `run_benchmark.py` - Benchmark runner with resource telemetry (uses real TR118 inference calls, seed control for reproducibility)
- `analyze_results.py` - Statistical analysis + comprehensive cost/energy calculations (multi-tier pricing, carbon footprint, efficiency metrics)
- `statistical_analysis.py` - **Frontier lab statistical rigor**: hypothesis testing (t-tests, ANOVA), effect sizes (Cohen's d), bootstrap CIs
- `visualize.py` - Advanced plots (latency, cost, energy efficiency, carbon footprint, cost vs throughput)
- `generate_report.py` - Publish-ready report generator with comprehensive cost/energy sections + statistical significance
- `validate_cost_energy.py` - Cost/energy validation (sanity checks)
- `cost_energy_analysis.py` - Deep-dive cost/energy analysis (ROI, TCO, amortization, efficiency rankings)
- `run_sweeps.py` - Sweep orchestration for multiple pricing/energy scenarios

### Utilities
- `artifact_utils.py` - Advanced cost/energy calculation helpers:
  - Multi-tier cost calculations (on-demand, spot, reserved)
  - Energy and carbon footprint calculations
  - TCO and ROI analysis
  - Break-even calculations
  - Energy efficiency scoring

### Configs
- `configs/baseline.yaml` - Baseline configuration
- `configs/smoke.yaml` - Fast smoke test
- `configs/matrix.yaml` - Comprehensive matrix
- `configs/variants/` - Pricing and energy scenario variants:
  - `pricing_tier1.yaml` - High-end cloud pricing (AWS p4d.24xlarge equivalent)
  - `pricing_tier2.yaml` - Mid-tier cloud pricing (AWS g4dn.xlarge equivalent)
  - `pricing_tier3.yaml` - Budget/on-premise pricing
  - `energy_renewable.yaml` - Renewable energy scenario
  - `energy_high_carbon.yaml` - High carbon intensity scenario

### Reproducibility
- `requirements.txt` - Python dependencies
- `Dockerfile` - Reproducible environment
- `EXPERIMENT_LOG.md` - Experiment tracking

## Quickstart

```bash
# Install dependencies
pip install -r scripts/tr119/requirements.txt

# Run smoke test
python scripts/tr119/run_experiment.py --config scripts/tr119/configs/smoke.yaml --device cuda

# Run full matrix
python scripts/tr119/run_experiment.py --config scripts/tr119/configs/matrix.yaml --device cuda

# Run cost/energy analysis
python scripts/tr119/cost_energy_analysis.py --config scripts/tr119/configs/baseline.yaml

# Run sweeps across pricing tiers
python scripts/tr119/run_sweeps.py --base-config scripts/tr119/configs/baseline.yaml
```

## Expected Deliverables

1. Multi-tier cost model with real cloud pricing
2. Energy measurements (±5% accuracy vs power meter)
3. TCO calculator (Python + web UI)
4. Carbon footprint analysis (gCO2e/token)
5. Technical report with production recommendations

## Features Implemented

### Statistical Rigor (Frontier Lab Quality)
- [x] 7 repetitions per configuration (configurable, default in baseline.yaml)
- [x] 95% confidence intervals (via TR117's statistical_analysis)
- [x] Hypothesis testing (t-tests, ANOVA) with p-values
- [x] Effect sizes (Cohen's d) for pairwise comparisons
- [x] Bootstrap confidence intervals
- [x] Outlier detection (IQR and Z-score methods)

### Cost & Energy Analysis
- [x] Real inference calls (reuses TR118's inference infrastructure)
- [x] Multi-tier pricing model (on-demand, spot, reserved)
- [x] Carbon footprint calculator (gCO2e per 1M tokens)
- [x] TCO calculator (infrastructure + energy costs)
- [x] ROI analysis (savings across pricing tiers)
- [x] Energy efficiency rankings (tokens per kWh)
- [x] Cost amortization analysis
- [x] Comprehensive cost metrics: $/hour, tokens/$, memory efficiency, compute efficiency

### Reproducibility
- [x] Seed control (configurable seed for random number generation)
- [x] Frozen dependencies (`requirements_frozen.txt`)
- [x] Docker environment (`Dockerfile`)
- [x] Experiment manifests with full environment capture

### Infrastructure
- [x] Sweep orchestration for multiple scenarios
- [x] Advanced visualizations (cost vs throughput, energy efficiency, carbon footprint)
- [x] Comprehensive report generation with cost/energy sections + statistical significance

## Next Steps

- [ ] Add cloud pricing fetcher (AWS/Azure/GCP APIs) for real-time pricing
- [ ] Add CPU-only cost/energy analysis
- [ ] Add multi-GPU cost analysis
- [ ] Run first end-to-end benchmark with real backends

## Timeline

- Week 1: Cost model + cloud pricing research
- Week 2: Energy measurement infrastructure
- Week 3: Benchmarking + analysis
- Week 4: Report writing

**Start Date:** TBD

