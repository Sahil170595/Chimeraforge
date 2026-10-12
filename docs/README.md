# Documentation Index

ChimeraForge is a model-agnostic **LLM deployment / capacity-planning CLI**: given
your hardware, workload, latency SLO, quality target, and budget, it recommends
the best (model x quantization x backend x GPU-instance-count) configuration --
backed by real benchmarks, with honest per-prediction provenance. It also bundles
the research harness (agent benchmarking, Rust vs Python, the TR series) that the
planner's data came from; those guides are archived below.

## The Planner CLI (start here)

- **[Installation](installation.md)** - install from PyPI, optional extras
- **[Quick Start](quick_start.md)** - first run in minutes
- **[Using the Planner](planning.md)** - `plan` / `suggest` / `measure` / `catalog`, end to end
- **[API Reference](API.md)** - the public Python API (`chimeraforge.planner`, resolver, discovery, measure)
- **[Trace regression gates](trace-regression-gate.md)** - unpublished 0.63.0 candidate, queue-inclusive saved evidence
- **[Serial trace campaigns](trace-campaign.md)** - unpublished 0.64.0 candidate, frozen ordered replica populations
- **[Signed contributions and private replay](signed-contribution-v2.md)** - unpublished 0.65.0 candidate, exact-byte signatures and explicit receiver trust
- **[Frozen prediction scorecards](prediction-scorecards.md)** - unpublished 0.66.0 candidate, explicit population and conditional native-rate error bands

```bash
pip install chimeraforge
chimeraforge plan --model Qwen/Qwen2.5-7B-Instruct --hardware "RTX 4090 24GB" --request-rate 2
chimeraforge suggest --source ollama --hardware "RTX 4080 12GB" --budget 500
chimeraforge measure --model qwen3:14b --ollama-url http://localhost:11434
```

25 commands: `plan`, `check`, `bundle`, `study`, `deploy`, `suggest`, `measure`,
`validate`, `catalog`, `safety`, `bench`, `trace`, `trace-campaign`, `gate`, `refit`, `compare`,
`score`, `eval`, `report`, `workload`, `monitor`, `doctor`, `contribute`, `mcp`, `serve`.
Run `chimeraforge --help` or `chimeraforge <cmd> --help`. The candidate adds
`gate --kind trace`; benchmark remains the default.

## Project Information

- **[Changelog](../CHANGELOG.md)** - version history
- **[Contributing](../CONTRIBUTING.md)** | **[Security](../SECURITY.md)** | **[Code of Conduct](../CODE_OF_CONDUCT.md)**

---

## Research Archive

ChimeraForge began as the public breakout of the Banterhearts performance-research
program (~204,000 measurements across TR108-TR137). These guides document that
research -- the agent-benchmarking harness, the language/runtime studies, and the
methodology behind the bundled data. They describe the code under
`src/python/banterhearts/` and `src/rust/`, **not** the planner CLI.

### Benchmarking & methodology
- **[Benchmarking Guide](archive/benchmarking.md)** - running the benchmark harness
- **[Methodology](archive/methodology.md)** - experimental design, isolation, cold starts
- **[Statistical Analysis](archive/statistical_analysis.md)** - sample sizes, CIs, rigor
- **[Technical Reports](archive/technical_reports.md)** - index of the TR series (TR108+)

### Agent research (Rust vs Python, multi-agent)
- **[Rust vs Python](archive/rust_vs_python.md)** - cross-language comparison (TR111-TR116)
- **[Rust Agents](archive/rust_agents.md)** / **[Python Agents](archive/python_agents.md)** - implementations
- **[Multi-Agent Guide](archive/multi_agent.md)** - concurrent execution scenarios
- **[Dual Ollama Setup](archive/dual_ollama_setup.md)** - required for the multi-agent experiments

### Optimization & structure
- **[Chimera Optimization](archive/chimera_optimization.md)** - config optimization (TR108)
- **[Performance Tuning](archive/performance_tuning.md)** - tuning techniques
- **[Architecture](archive/ARCHITECTURE.md)** - the agent/research subsystem architecture
- **[Repository Structure](archive/repo_structure.md)** - folder layout & data governance
- **[FAQ](archive/faq.md)** - common questions

The canonical technical-report archive lives in `outputs/publish_ready/reports/`.

---

## Documentation Standards

- ASCII-only for universal compatibility
- Commands assume execution from the repository root unless noted
- Links are relative to this `docs/` directory

Published CLI: **0.61.0**. This checkout prepares **0.66.0**; the linked 0.62.0-0.66.0
candidate features require their source or wheels until release. See the
[Changelog](../CHANGELOG.md) for version history.
